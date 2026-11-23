"""
Vòng lặp hội thoại của Agent-BE. Nhận lịch sử + câu hỏi mới, gọi model kèm tool
registry, tự chạy tool READ, và với tool "propose" thì CHỈ thu thẻ đề xuất để
người dùng xác nhận trên giao diện — không bao giờ tự ghi dữ liệu kế toán
(ranh giới cứng, xem KE_HOACH_HE_THONG_KE_TOAN.md mục 8.2).

Provider chọn qua AGENT_PROVIDER: "claude" (Anthropic SDK) hoặc "nim"/"ollama"
(đều là OpenAI-compatible). Gọi SDK trực tiếp, không dùng framework agent — đúng
khuyến nghị của Anthropic "Building Effective Agents": giữ trace/prompt minh bạch.

Lịch sử trả về/nhận vào là text thuần (user/assistant) nên đổi provider giữa
chừng không bị lệch định dạng; kết quả tool của lượt trước không được giữ lại
(ponytail: nếu cần hỏi nối tiếp dựa trên số liệu cũ, model sẽ gọi lại tool).
"""
import json
import re

import anthropic
import openai
from sqlalchemy.orm import Session

from app.config import settings
from app.agent.tools import AGENT_TOOLS, TOOL_HANDLERS, TOOL_CATEGORY

MAX_TOOL_ITERATIONS = 6  # chặn vòng lặp vô hạn nếu model cứ gọi tool liên tục
MAX_HISTORY_TURNS = 20   # chỉ giữ N lượt gần nhất để prompt không phình mãi
TOO_MANY_STEPS_REPLY = "Xin lỗi, câu hỏi này cần tra cứu nhiều bước quá — bạn thử hỏi cụ thể/ngắn gọn hơn nhé."

SYSTEM_PROMPT = """\
Bạn là trợ lý kế toán nội bộ cho 1 công ty thu mua nông sản (chủ yếu mủ cao su, điều thô) tại Việt Nam. \
Trả lời NGẮN GỌN, TRỰC TIẾP bằng tiếng Việt, đúng trọng tâm câu hỏi — đây là công cụ nội bộ dùng \
hàng ngày, không phải hội thoại xã giao. \
Luôn dùng tool để tra cứu số liệu thật, KHÔNG được tự đoán hay bịa số liệu. \
Nếu không chắc tên người bán, gọi search_seller trước để xác nhận đúng người rồi mới tra cứu tiếp. \
Khi người dùng muốn tạo phiếu chi, gọi propose_voucher_draft: tool này chỉ hiện thẻ đề xuất, \
CHƯA tạo phiếu. Sau đó nói ngắn gọn là đã soạn nháp và nhắc người dùng kiểm tra rồi bấm Lưu — \
tuyệt đối không nói là đã tạo/lưu phiếu. \
Các thao tác ghi khác (sửa/huỷ/duyệt phiếu) chưa hỗ trợ qua chat: nói rõ và đề nghị người dùng vào đúng trang."""

# Tool trả về cho model biết thẻ đã hiện — model không thấy "thành công ghi DB" nên không nói dối.
PROPOSAL_NOTE = "Thẻ đề xuất ĐÃ hiện cho người dùng, phiếu CHƯA được tạo. Người dùng phải tự kiểm tra và bấm Lưu."


class AgentTurnResult:
    def __init__(self, reply: str, history: list[dict], tool_calls_made: list[str], proposals: list[dict] | None = None):
        self.reply = reply
        self.history = history
        self.tool_calls_made = tool_calls_made
        self.proposals = proposals or []


def _clean_history(history: list[dict] | None) -> list[dict]:
    """Chỉ nhận lượt user/assistant có nội dung text — bỏ mọi thứ lạ client gửi lên (trust boundary)."""
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"]
    ]
    return clean[-MAX_HISTORY_TURNS:]


def _safe_context(context: str | None) -> str | None:
    """Context do client gửi (đường dẫn trang) — lọc ký tự lạ + cắt ngắn để không thành đường prompt-injection."""
    if not context:
        return None
    return re.sub(r"[^\w/\-]", "", context)[:60] or None


def _run_tool(db: Session, name: str, args: dict, proposals: list[dict]) -> dict:
    category = TOOL_CATEGORY.get(name)
    if category not in ("read", "propose"):
        return {"error": f"Tool '{name}' không được phép tự thực thi."}
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Không rõ tool '{name}'"}
    try:
        result = handler(db, **args)
    except Exception as e:  # noqa: BLE001 - muốn agent thấy lỗi để tự giải thích lại cho người dùng, không crash cả request
        return {"error": f"Lỗi khi chạy tool: {e}"}
    if category == "propose" and "proposal" in result:
        proposals.append(result["proposal"])
        return {"trang_thai": "da_hien_the_de_xuat", "luu_y": PROPOSAL_NOTE, **result["proposal"]}
    return result


def _loop_claude(db: Session, system: str, messages: list[dict], proposals: list[dict], tool_calls_made: list[str]) -> str:
    if not settings.anthropic_api_key:
        raise RuntimeError("Chưa cấu hình ANTHROPIC_API_KEY trong .env — Agent-BE cần key này khi dùng AGENT_PROVIDER=claude.")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=settings.scan_extraction_model,
            max_tokens=1024,
            system=system,
            tools=AGENT_TOOLS,
            messages=messages,
        )
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            return "".join(b.text for b in response.content if b.type == "text")

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in tool_use_blocks:
            result = _run_tool(db, block.name, block.input, proposals)
            tool_calls_made.append(block.name)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, ensure_ascii=False)}
            )
        messages.append({"role": "user", "content": tool_results})
    return TOO_MANY_STEPS_REPLY


def _loop_openai_compatible(
    db: Session, provider: str, system: str, messages: list[dict], proposals: list[dict], tool_calls_made: list[str]
) -> str:
    if provider == "nim":
        if not settings.nim_api_key:
            raise RuntimeError("Chưa cấu hình NIM_API_KEY trong .env — Agent-BE cần key này khi dùng AGENT_PROVIDER=nim.")
        client = openai.OpenAI(api_key=settings.nim_api_key, base_url=settings.nim_base_url, timeout=60.0)
        model = settings.agent_nim_model
    else:
        client = openai.OpenAI(api_key="ollama", base_url=f"{settings.ollama_base_url.rstrip('/')}/v1", timeout=120.0)
        model = settings.agent_ollama_model

    tools = [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in AGENT_TOOLS
    ]
    msgs = [{"role": "system", "content": system}] + messages
    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            resp = client.chat.completions.create(model=model, max_tokens=1024, tools=tools, messages=msgs)
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""

            msgs.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = None
                if isinstance(args, dict):
                    result = _run_tool(db, tc.function.name, args, proposals)
                else:
                    result = {"error": "Tham số tool không phải JSON object hợp lệ — gọi lại đúng định dạng"}
                tool_calls_made.append(tc.function.name)
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, ensure_ascii=False)})
    except openai.OpenAIError as e:
        raise RuntimeError(f"Lỗi gọi model {provider}: {e}")
    return TOO_MANY_STEPS_REPLY


def run_agent_turn(
    db: Session, user_message: str, history: list[dict] | None = None, context: str | None = None
) -> AgentTurnResult:
    provider = (settings.agent_provider or "claude").strip().lower()
    ctx = _safe_context(context)
    system = SYSTEM_PROMPT + (f"\n\nNgười dùng đang mở trang: {ctx}." if ctx else "")

    turns = _clean_history(history)
    turns.append({"role": "user", "content": user_message})

    proposals: list[dict] = []
    tool_calls_made: list[str] = []
    working = list(turns)  # vòng lặp tự thêm tool_use/tool_result vào bản này, không đụng `turns`

    if provider in ("claude", "anthropic"):
        reply = _loop_claude(db, system, working, proposals, tool_calls_made)
    elif provider in ("nim", "ollama"):
        reply = _loop_openai_compatible(db, provider, system, working, proposals, tool_calls_made)
    else:
        raise RuntimeError(f"AGENT_PROVIDER không hợp lệ: '{provider}'. Chỉ chấp nhận 'claude', 'nim' hoặc 'ollama'.")

    turns.append({"role": "assistant", "content": reply})
    return AgentTurnResult(reply=reply, history=turns, tool_calls_made=tool_calls_made, proposals=proposals)
