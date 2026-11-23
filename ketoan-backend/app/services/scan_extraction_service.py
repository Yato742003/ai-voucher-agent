"""
Trích xuất dữ liệu từ ảnh bảng kê viết tay (Mẫu 02/TNDN) bằng Claude vision
hoặc Llama-3.2-90B qua NVIDIA NIM (OpenAI-compatible), kèm 2 lớp kiểm tra
chéo để giảm rủi ro model đọc nhầm chữ số (xem thảo luận trong
KE_HOACH_NANG_CAP_UX_TINH_NANG.md — vision model KHÔNG có confidence
score đáng tin cậy, nên không dùng riêng nó để tạo phiếu chi tự động).

QUAN TRỌNG: hàm ở đây KHÔNG tự tạo phiếu chi. Nó chỉ trả về danh sách dòng
đã trích xuất kèm cờ cảnh báo — người dùng luôn phải xem/sửa/xác nhận qua
API /scans/{id}/confirm (app/api/scans.py) trước khi phiếu thật được tạo.

Dữ liệu (ảnh gốc + kết quả thô + kết quả đã sửa) được lưu lại trong bảng
scan_imports — đây chính là kho dữ liệu gán nhãn để sau này fine-tune 1
model OCR riêng cho chữ viết tay của công ty (xem kế hoạch, mục "training
OCR riêng"), một khi đã tích luỹ đủ (bạn có sẵn ~180 ảnh cũ có thể chạy
qua pipeline này để bootstrap ngay).

Provider được chọn qua biến SCAN_PROVIDER trong .env:
  - "claude" (mặc định): gọi Anthropic API với tool_use
  - "nim": gọi NVIDIA NIM (meta/llama-3.2-90b-vision-instruct hoặc model khác)
           qua OpenAI-compatible API với JSON structured output
"""
import base64
import json
from decimal import Decimal, InvalidOperation

import anthropic
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.services.fuzzy_match_service import find_possible_duplicates

ARITHMETIC_TOLERANCE_PCT = 0.03  # cho phép lệch 3% giữa so_luong*don_gia và tong_tien (làm tròn/phụ phí)

# ---------------------------------------------------------------------------
# Schema dùng chung cho cả 2 provider
# ---------------------------------------------------------------------------

EXTRACTION_TOOL = {
    "name": "record_bang_ke_rows",
    "description": "Ghi lại các dòng dữ liệu đã đọc được từ ảnh bảng kê thu mua hàng hoá viết tay.",
    "input_schema": {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "description": "Mỗi phần tử là 1 dòng trong bảng (1 người bán), theo đúng thứ tự từ trên xuống.",
                "items": {
                    "type": "object",
                    "properties": {
                        "ten_nguoi_ban": {"type": "string", "description": "Tên người bán, giữ nguyên dấu tiếng Việt, viết đầy đủ nếu đoán được chữ viết tắt (VD 'Ng' -> 'Nguyễn')"},
                        "ten_hang_hoa": {"type": "string", "description": "Tên hàng hoá, VD 'Mủ nước'. Nếu cột này để trống/gộp ở đầu bảng thì lặp lại giá trị đó cho mọi dòng."},
                        "so_luong": {"type": "number", "description": "Số lượng/trọng lượng, đơn vị kg"},
                        "don_gia": {"type": "number"},
                        "tong_gia_thanh_toan": {"type": "number"},
                        "do_tin_cay_thap": {"type": "boolean", "description": "true nếu chữ viết mờ/khó đọc và bạn không chắc chắn đã đọc đúng"},
                    },
                    "required": ["ten_nguoi_ban", "so_luong", "don_gia", "tong_gia_thanh_toan"],
                },
            }
        },
        "required": ["rows"],
    },
}

EXTRACTION_PROMPT = """\
Đây là ảnh chụp 1 "Bảng kê thu mua hàng hóa, dịch vụ mua vào không có hóa đơn" \
(Mẫu 02/TNDN) viết tay của 1 công ty thu mua nông sản Việt Nam. \
Hãy đọc từng dòng trong bảng (mỗi dòng là 1 người bán) và gọi tool record_bang_ke_rows \
để ghi lại. Đọc đúng theo thứ tự từ trên xuống dưới, không bỏ sót dòng nào có dữ liệu. \
Nếu 1 dòng không đọc được rõ tên người bán hoặc số liệu, vẫn ghi lại theo cách đọc tốt \
nhất có thể và đánh dấu do_tin_cay_thap = true cho dòng đó."""

# Prompt dùng cho NIM (không hỗ trợ tool_use -> yêu cầu trả về JSON thuần)
NIM_EXTRACTION_PROMPT = """\
Đây là ảnh chụp 1 "Bảng kê thu mua hàng hóa, dịch vụ mua vào không có hóa đơn" \
(Mẫu 02/TNDN) viết tay của 1 công ty thu mua nông sản Việt Nam. \
Hãy đọc từng dòng trong bảng (mỗi dòng là 1 người bán) theo đúng thứ tự từ trên xuống, \
không bỏ sót dòng nào có dữ liệu. \
Nếu 1 dòng không đọc được rõ, vẫn ghi lại theo cách đọc tốt nhất và đặt do_tin_cay_thap=true.

Trả về ĐÚNG định dạng JSON sau, KHÔNG kèm markdown hay giải thích:
{
  "rows": [
    {
      "ten_nguoi_ban": "...",
      "ten_hang_hoa": "...",
      "so_luong": 0,
      "don_gia": 0,
      "tong_gia_thanh_toan": 0,
      "do_tin_cay_thap": false
    }
  ]
}"""


# Cùng cấu trúc với EXTRACTION_TOOL["input_schema"], nhưng ở dạng JSON Schema
# thuần cho tham số `format` của Ollama (model local không dùng tool-calling
# đáng tin cậy như Claude, nên ép cấu trúc JSON ở tầng response thay vì tool).
OLLAMA_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ten_nguoi_ban": {"type": "string"},
                    "ten_hang_hoa": {"type": "string"},
                    "so_luong": {"type": "number"},
                    "don_gia": {"type": "number"},
                    "tong_gia_thanh_toan": {"type": "number"},
                    "do_tin_cay_thap": {"type": "boolean"},
                },
                "required": ["ten_nguoi_ban", "so_luong", "don_gia", "tong_gia_thanh_toan"],
            },
        }
    },
    "required": ["rows"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _media_type_from_filename(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")


# ---------------------------------------------------------------------------
# Provider: Claude (Anthropic) — dùng tool_use để buộc output có cấu trúc
# ---------------------------------------------------------------------------

def _extract_via_claude(image_bytes: bytes, filename: str) -> list[dict]:
    """Gọi Claude vision qua Anthropic SDK, trả về danh sách dòng thô."""
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "Chưa cấu hình ANTHROPIC_API_KEY trong .env — "
            "tính năng scan bảng kê cần key này khi dùng SCAN_PROVIDER=claude."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    media_type = _media_type_from_filename(filename)

    try:
        response = client.messages.create(
            model=settings.scan_extraction_model,
            max_tokens=4096,
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "record_bang_ke_rows"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }
            ],
        )
    except anthropic.RateLimitError as e:
        raise RuntimeError(
            f"Hết hạn mức (quota) API Anthropic — thử lại sau vài phút. Chi tiết: {e}"
        )
    except anthropic.APIConnectionError as e:
        raise RuntimeError(
            f"Không kết nối được tới API Anthropic — kiểm tra kết nối mạng. Chi tiết: {e}"
        )
    except anthropic.APIStatusError as e:
        raise RuntimeError(
            f"API Anthropic trả lỗi ({e.status_code}) — {e.message}"
        )

    for block in response.content:
        if block.type == "tool_use" and block.name == "record_bang_ke_rows":
            return block.input.get("rows", [])

    raise RuntimeError("Claude không trả về dữ liệu trích xuất — thử lại hoặc chụp ảnh rõ hơn.")


# ---------------------------------------------------------------------------
# Provider: NVIDIA NIM — OpenAI-compatible, JSON structured output
# ---------------------------------------------------------------------------

def _extract_via_nim(image_bytes: bytes, filename: str) -> list[dict]:
    """
    Gọi NVIDIA NIM (meta/llama-3.2-90b-vision-instruct hoặc model khác được
    cấu hình trong NIM_EXTRACTION_MODEL) qua OpenAI-compatible API.
    NIM không hỗ trợ tool_use nên dùng JSON prompt + response_format.
    """
    if not settings.nim_api_key:
        raise RuntimeError(
            "Chưa cấu hình NIM_API_KEY trong .env — "
            "tính năng scan bảng kê cần key này khi dùng SCAN_PROVIDER=nim. "
            "Lấy key tại: https://build.nvidia.com"
        )

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "Thư viện 'openai' chưa được cài — chạy: pip install openai>=1.0.0"
        )

    client = OpenAI(
        api_key=settings.nim_api_key,
        base_url=settings.nim_base_url,
        timeout=60.0,
    )
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    media_type = _media_type_from_filename(filename)

    try:
        import openai as openai_errors
    except ImportError:
        openai_errors = None  # type: ignore[assignment]

    try:
        response = client.chat.completions.create(
            model=settings.nim_extraction_model,
            max_tokens=4096,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                        },
                        {"type": "text", "text": NIM_EXTRACTION_PROMPT},
                    ],
                }
            ],
        )
    except Exception as e:
        # Phân loại lỗi từ openai SDK nếu import được
        if openai_errors is not None:
            if isinstance(e, openai_errors.RateLimitError):
                raise RuntimeError(
                    f"Hết hạn mức (quota) NVIDIA NIM API — thử lại sau vài phút. Chi tiết: {e}"
                )
            if isinstance(e, openai_errors.APITimeoutError):
                raise RuntimeError(
                    f"Thời gian chờ (timeout) NVIDIA NIM API quá 60s — thử lại hoặc giảm kích thước ảnh. Chi tiết: {e}"
                )
            if isinstance(e, openai_errors.APIConnectionError):
                raise RuntimeError(
                    f"Lỗi kết nối mạng tới NVIDIA NIM API. Chi tiết: {e}"
                )
            if isinstance(e, openai_errors.APIStatusError):
                raise RuntimeError(
                    f"NVIDIA NIM API trả lỗi ({e.status_code}) — {e.message}"  # type: ignore[attr-defined]
                )
        raise RuntimeError(f"Lỗi gọi NVIDIA NIM API: {e}")

    raw_content = response.choices[0].message.content or ""
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"NIM trả về JSON không hợp lệ — thử lại hoặc chụp ảnh rõ hơn. Chi tiết: {exc}"
        )

    rows = data.get("rows", [])
    if not isinstance(rows, list):
        raise RuntimeError("NIM trả về dữ liệu không đúng định dạng — thiếu key 'rows'.")

    return rows


# ---------------------------------------------------------------------------
# Provider: Ollama — Local vision model fallback
# ---------------------------------------------------------------------------

def _extract_via_ollama(image_bytes: bytes, filename: str) -> list[dict]:
    """
    Gọi model vision chạy local qua Ollama (mặc định gemma3:4b). Dùng
    endpoint /api/chat với `format` là JSON schema để ép model trả JSON
    đúng cấu trúc — model nhỏ không đáng tin cậy với tool-calling như
    Claude, nên ép format ở tầng response là cách chắc ăn hơn.
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    request_body = {
        "model": settings.ollama_vision_model,
        "messages": [{"role": "user", "content": EXTRACTION_PROMPT, "images": [image_b64]}],
        "stream": False,
        "format": OLLAMA_JSON_SCHEMA,
    }

    try:
        resp = httpx.post(f"{settings.ollama_base_url}/api/chat", json=request_body, timeout=120)
        resp.raise_for_status()
    except httpx.ConnectError:
        raise RuntimeError(
            f"Không kết nối được tới Ollama tại {settings.ollama_base_url} — kiểm tra Ollama đã chạy chưa "
            f"(lệnh `ollama serve`) và đã `ollama pull {settings.ollama_vision_model}` chưa."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Ollama trả lỗi: {e.response.status_code} — {e.response.text[:300]}")

    content = resp.json().get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(f"Model local trả về không đúng định dạng JSON — thử lại hoặc dùng provider khác. Nội dung: {content[:300]}")

    return parsed.get("rows", [])


# ---------------------------------------------------------------------------
# Public API — dispatch theo SCAN_PROVIDER
# ---------------------------------------------------------------------------

def extract_bang_ke_from_image(image_bytes: bytes, filename: str) -> tuple[list[dict], str, str]:
    """
    Trích xuất bảng kê từ ảnh. Provider được chọn qua settings.scan_provider:
      - "claude" (hoặc "anthropic"): dùng Anthropic Claude (mặc định, ANTHROPIC_API_KEY)
      - "nim"                      : dùng NVIDIA NIM / Llama-3.2-90B (NIM_API_KEY)
      - "ollama"                   : dùng local Ollama vision model (ollama_vision_model)
    Trả về tuple (rows, provider_name, model_name) để lưu vào database phục vụ benchmark sau này.
    """
    provider = (settings.scan_extraction_provider or settings.scan_provider or "claude").strip().lower()
    if provider == "nim":
        rows = _extract_via_nim(image_bytes, filename)
        return rows, "nim", settings.nim_extraction_model
    elif provider in ("claude", "anthropic"):
        rows = _extract_via_claude(image_bytes, filename)
        return rows, "claude", settings.scan_extraction_model
    elif provider == "ollama":
        rows = _extract_via_ollama(image_bytes, filename)
        return rows, "ollama", settings.ollama_vision_model
    else:
        raise RuntimeError(
            f"SCAN_PROVIDER không hợp lệ: '{provider}'. Chỉ chấp nhận 'claude', 'anthropic', 'nim' hoặc 'ollama'."
        )


def validate_extracted_rows(db: Session, rows: list[dict]) -> list[dict]:
    """
    Thêm cờ cảnh báo vào từng dòng:
      - canh_bao_phep_nhan: số lượng * đơn giá không khớp tổng tiền
      - canh_bao_ten_khong_khop: tên người bán không giống ai trong danh sách hiện có
      - seller_id_goi_y: nếu có 1 người bán khớp gần đúng, gợi ý sẵn id đó
    KHÔNG tự sửa dữ liệu — chỉ đánh dấu để người dùng tự quyết.
    """
    validated = []
    for row in rows:
        row = dict(row)

        so_luong = _to_decimal(row.get("so_luong"))
        don_gia = _to_decimal(row.get("don_gia"))
        tong_tien = _to_decimal(row.get("tong_gia_thanh_toan"))

        canh_bao_phep_nhan = False
        if so_luong is not None and don_gia is not None and tong_tien not in (None, 0):
            expected = so_luong * don_gia
            diff_pct = abs(expected - tong_tien) / tong_tien if tong_tien else 1
            canh_bao_phep_nhan = diff_pct > ARITHMETIC_TOLERANCE_PCT
        row["canh_bao_phep_nhan"] = canh_bao_phep_nhan

        ten = (row.get("ten_nguoi_ban") or "").strip()
        seller_id_goi_y = None
        canh_bao_ten_khong_khop = True
        if ten:
            candidates = find_possible_duplicates(db, ten, limit=1)
            if candidates:
                seller, score = candidates[0]
                if score >= 95:
                    seller_id_goi_y = str(seller.id)
                    canh_bao_ten_khong_khop = False
        row["seller_id_goi_y"] = seller_id_goi_y
        row["canh_bao_ten_khong_khop"] = canh_bao_ten_khong_khop

        validated.append(row)

    return validated


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
