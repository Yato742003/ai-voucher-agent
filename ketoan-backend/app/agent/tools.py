"""
Tool registry cho Agent-BE. Mỗi tool có:
  - schema: định nghĩa gửi cho Claude (tên, mô tả, input_schema)
  - category: "read" (agent tự chạy) hoặc "write" (luôn cần người xác nhận
    — xem ranh giới cứng trong KE_HOACH_HE_THONG_KE_TOAN.md mục 8.2)
  - handler: hàm Python thật sự thực thi, LUÔN đi qua service layer có
    sẵn (không viết SQL/logic nghiệp vụ mới ở đây)

Loại tool:
  - "read": chỉ đọc, agent tự chạy.
  - "propose": KHÔNG ghi DB — chỉ trả về 1 thẻ đề xuất để người dùng xem/sửa/xác nhận trên
    giao diện. Việc ghi thật đi qua đúng API người dùng (POST /vouchers/) nên chịu mọi
    ràng buộc RBAC/audit như thao tác tay (xem mục 8.2 kế hoạch).
Chưa có loại "write" tự thực thi — và cố ý không có.
"""
import re
from datetime import date, timedelta
from statistics import median

from sqlalchemy import select, extract
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.sales_invoice import SalesInvoice, SalesInvoiceStatus
from app.models.seller import Seller, normalize_name
from app.models.voucher import Voucher, VoucherStatus
from app.services.fuzzy_match_service import find_possible_duplicates
from app.services.scan_extraction_service import ARITHMETIC_TOLERANCE_PCT
from app.services.watchdog_service import price_deviation

SEARCH_SELLER_TOOL = {
    "name": "search_seller",
    "description": (
        "Tìm người bán (nông dân/nhà cung cấp) trong hệ thống theo tên, kể cả gõ không dấu hoặc "
        "gõ tắt. Dùng khi cần biết 1 người bán có tồn tại trong hệ thống không, hoặc tìm đúng ID "
        "của họ trước khi trả lời câu hỏi liên quan đến người đó."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Tên người bán cần tìm (có thể không dấu/gõ tắt)"},
        },
        "required": ["query"],
    },
}

GET_MONTHLY_SUMMARY_TOOL = {
    "name": "get_monthly_summary",
    "description": (
        "Tra cứu tổng số tiền và số phiếu chi trong 1 tháng — có thể lọc theo 1 người bán cụ thể "
        "(dùng search_seller trước để có đúng tên nếu không chắc), hoặc để trống để xem tổng toàn "
        "công ty. Dùng cho các câu hỏi kiểu 'tháng này đã chi bao nhiêu', 'đã trả cho anh X bao nhiêu'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "month": {"type": "integer", "description": "Tháng (1-12)"},
            "year": {"type": "integer", "description": "Năm, VD 2026"},
            "seller_name": {"type": "string", "description": "Tên người bán để lọc riêng — bỏ trống nếu hỏi tổng toàn công ty"},
        },
        "required": ["month", "year"],
    },
}

GET_RECEIVABLES_TOOL = {
    "name": "get_receivables",
    "description": (
        "Tra công nợ phải thu: các hoá đơn bán ra đã xuất nhưng khách chưa trả tiền. Có thể lọc theo "
        "1 khách hàng (gõ đúng dấu tên công ty), hoặc để trống để xem toàn bộ. Dùng cho câu hỏi kiểu "
        "'ai còn nợ mình', 'Đối tác A còn nợ bao nhiêu'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_name": {"type": "string", "description": "Tên khách hàng (1 phần tên cũng được) — bỏ trống nếu xem tất cả"},
        },
    },
}

GET_PRICE_HISTORY_TOOL = {
    "name": "get_price_history",
    "description": (
        "Tra lịch sử đơn giá thu mua (đồng/kg) từ các phiếu chi có ghi đơn giá: thấp nhất, cao nhất, "
        "trung vị, lần mua gần nhất. Lọc theo 1 người bán hoặc toàn công ty. Dùng cho câu hỏi kiểu "
        "'giá mua dạo này thế nào', 'anh Kiếm bán giá bao nhiêu'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "seller_name": {"type": "string", "description": "Tên người bán — bỏ trống nếu xem toàn công ty"},
            "months": {"type": "integer", "description": "Số tháng nhìn lại (1-24), mặc định 3"},
        },
    },
}

PROPOSE_VOUCHER_TOOL = {
    "name": "propose_voucher_draft",
    "description": (
        "Soạn 1 phiếu chi NHÁP từ câu của người dùng (VD 'mua 500kg mủ anh Kiếm giá 15.000'). Tool này "
        "KHÔNG tạo phiếu — nó chỉ hiện 1 thẻ đề xuất để người dùng kiểm tra/sửa rồi tự bấm Lưu. "
        "Cần ít nhất: tên người bán, lý do chi, và số tiền (hoặc cả số lượng + đơn giá)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "seller_name": {"type": "string", "description": "Tên người bán (có thể không dấu/gõ tắt)"},
            "ly_do_chi": {"type": "string", "description": "VD 'Mua mủ cao su nước'"},
            "so_luong": {"type": "number", "description": "Số lượng, kg"},
            "don_gia": {"type": "number", "description": "Đơn giá, đồng/kg"},
            "so_tien": {"type": "number", "description": "Tổng tiền, đồng — bỏ trống nếu đã có số lượng và đơn giá"},
            "ngay": {"type": "string", "description": "Ngày chi dạng YYYY-MM-DD — bỏ trống nghĩa là hôm nay"},
        },
        "required": ["seller_name", "ly_do_chi"],
    },
}

AGENT_TOOLS = [
    SEARCH_SELLER_TOOL, GET_MONTHLY_SUMMARY_TOOL, GET_RECEIVABLES_TOOL, GET_PRICE_HISTORY_TOOL, PROPOSE_VOUCHER_TOOL,
]
TOOL_CATEGORY = {
    "search_seller": "read",
    "get_monthly_summary": "read",
    "get_receivables": "read",
    "get_price_history": "read",
    "propose_voucher_draft": "propose",
}


_HONORIFICS = {"anh", "chi", "chu", "co", "bac", "ong", "ba", "em"}


def _match_by_normalized(db: Session, normalized: str, limit: int, whole_word: bool = False) -> list[Seller]:
    if not normalized:
        return []
    stmt = select(Seller).where(
        Seller.alias_of_seller_id.is_(None),
        Seller.name_normalized.ilike(f"%{normalized}%"),
    )
    if not whole_word:
        return db.execute(stmt.limit(limit)).scalars().all()
    rows = db.execute(stmt).scalars().all()
    pattern = re.compile(rf"\b{re.escape(normalized)}\b")
    return [s for s in rows if pattern.search(s.name_normalized)][:limit]


def _find_sellers(db: Session, query: str, limit: int) -> list[tuple[Seller, float | None]]:
    """
    Tìm người bán khớp với `query`:
      1) Fuzzy match toàn tên (chịu lỗi chính tả/thiếu dấu >= 85%).
      2) Substring trên `name_normalized` (không dùng ILIKE trên `name` thô vì
         PostgreSQL ILIKE không tự bỏ dấu tiếng Việt).
      3) Fallback bỏ danh xưng Việt Nam ('anh Kiếm', 'chú Ba'...) và khớp trọn từ
         để tránh 'chú Ba' khớp nhầm vào 'Bảo'.
    """
    candidates = find_possible_duplicates(db, query, limit=limit)
    if candidates:
        return [(s, score) for s, score in candidates]

    norm = normalize_name(query)
    if not norm:
        return []

    rows = _match_by_normalized(db, norm, limit)
    if rows:
        return [(s, None) for s in rows]

    parts = norm.split()
    if len(parts) >= 2 and parts[0] in _HONORIFICS:
        stripped = " ".join(parts[1:])
        candidates = find_possible_duplicates(db, stripped, limit=limit)
        if candidates:
            return [(s, score) for s, score in candidates]
        rows = _match_by_normalized(db, stripped, limit, whole_word=True)
        if rows:
            return [(s, None) for s in rows]

    return []


def _resolve_seller_by_name(db: Session, query: str) -> Seller | None:
    matches = _find_sellers(db, query, limit=1)
    return matches[0][0] if matches else None


def handle_search_seller(db: Session, query: str) -> dict:
    matches = _find_sellers(db, query, limit=5)
    if not matches:
        return {"found": False, "message": f"Không tìm thấy người bán nào khớp với '{query}'"}
    return {
        "found": True,
        "sellers": [
            {"id": str(s.id), "name": s.name, **({"do_khop_pct": round(score, 1)} if score is not None else {})}
            for s, score in matches
        ],
    }


def handle_get_monthly_summary(db: Session, month: int, year: int, seller_name: str | None = None) -> dict:
    if not (1 <= month <= 12):
        return {"error": "Tháng phải từ 1 đến 12"}

    stmt = select(Voucher).where(
        extract("month", Voucher.ngay) == month,
        extract("year", Voucher.ngay) == year,
        Voucher.trang_thai != VoucherStatus.VOID,
    )

    matched_seller_name = None
    if seller_name:
        seller = _resolve_seller_by_name(db, seller_name)
        if seller is None:
            return {"error": f"Không tìm thấy người bán nào khớp với '{seller_name}' — thử gọi search_seller trước để xác nhận tên đúng"}
        matched_seller_name = seller.name
        stmt = stmt.where(Voucher.seller_id == seller.id)

    vouchers = db.execute(stmt).scalars().all()
    tong_tien = sum(float(v.so_tien) for v in vouchers)

    return {
        "thang": month,
        "nam": year,
        "nguoi_ban": matched_seller_name,  # None nghĩa là tổng toàn công ty
        "tong_so_tien": tong_tien,
        "so_luong_phieu": len(vouchers),
    }


def handle_get_receivables(db: Session, customer_name: str | None = None) -> dict:
    stmt = select(SalesInvoice).where(
        SalesInvoice.trang_thai == SalesInvoiceStatus.ISSUED,
        SalesInvoice.paid_at.is_(None),
    )
    matched_name = None
    if customer_name:
        # ponytail: ILIKE trên tên gốc (Customer chưa có cột name_normalized) — phải gõ đúng dấu.
        customers = db.execute(
            select(Customer).where(Customer.company_name.ilike(f"%{customer_name.strip()}%"))
        ).scalars().all()
        if not customers:
            return {"error": f"Không tìm thấy khách hàng nào khớp với '{customer_name}' (thử gõ đúng dấu tên công ty)"}
        matched_name = ", ".join(c.company_name for c in customers)
        stmt = stmt.where(SalesInvoice.customer_id.in_([c.id for c in customers]))

    invoices = db.execute(stmt).scalars().all()
    by_customer: dict = {}
    for inv in invoices:
        e = by_customer.setdefault(inv.customer.company_name, {"so_hoa_don": 0, "tong_tien": 0.0, "cu_nhat": inv.ngay})
        e["so_hoa_don"] += 1
        e["tong_tien"] += float(inv.tong_tien)
        e["cu_nhat"] = min(e["cu_nhat"], inv.ngay)

    return {
        "khach_hang_loc": matched_name,
        "so_hoa_don_chua_thu": len(invoices),
        "tong_cong_no": sum(e["tong_tien"] for e in by_customer.values()),
        "theo_khach_hang": [
            {"khach_hang": name, "so_hoa_don": e["so_hoa_don"], "tong_tien": e["tong_tien"], "hoa_don_cu_nhat": e["cu_nhat"].isoformat()}
            for name, e in sorted(by_customer.items(), key=lambda kv: kv[1]["tong_tien"], reverse=True)
        ],
    }


def handle_get_price_history(db: Session, seller_name: str | None = None, months: int = 3) -> dict:
    if not (1 <= months <= 24):
        return {"error": "Số tháng phải từ 1 đến 24"}

    stmt = select(Voucher).where(
        Voucher.don_gia.is_not(None),
        Voucher.trang_thai != VoucherStatus.VOID,
        Voucher.ngay >= date.today() - timedelta(days=30 * months),
    )
    matched_name = None
    if seller_name:
        seller = _resolve_seller_by_name(db, seller_name)
        if seller is None:
            return {"error": f"Không tìm thấy người bán nào khớp với '{seller_name}' — thử gọi search_seller trước để xác nhận tên đúng"}
        matched_name = seller.name
        stmt = stmt.where(Voucher.seller_id == seller.id)

    vouchers = db.execute(stmt.order_by(Voucher.ngay.desc())).scalars().all()
    if not vouchers:
        return {"nguoi_ban": matched_name, "so_phieu": 0, "message": f"Không có phiếu nào ghi đơn giá trong {months} tháng gần đây"}

    prices = [float(v.don_gia) for v in vouchers]
    return {
        "nguoi_ban": matched_name,
        "so_thang": months,
        "so_phieu": len(vouchers),
        "don_gia_thap_nhat": min(prices),
        "don_gia_cao_nhat": max(prices),
        "don_gia_trung_vi": median(prices),
        "don_gia_gan_nhat": prices[0],
        "ngay_gan_nhat": vouchers[0].ngay.isoformat(),
    }


def handle_propose_voucher_draft(
    db: Session,
    seller_name: str,
    ly_do_chi: str,
    so_luong: float | None = None,
    don_gia: float | None = None,
    so_tien: float | None = None,
    ngay: str | None = None,
) -> dict:
    """KHÔNG ghi DB. Trả {"proposal": {...}} — người dùng xác nhận qua POST /vouchers/."""
    if not (ly_do_chi or "").strip():
        return {"error": "Thiếu lý do chi"}
    try:
        ngay_d = date.fromisoformat(ngay) if ngay else date.today()
    except ValueError:
        return {"error": f"Ngày '{ngay}' không đúng định dạng YYYY-MM-DD"}
    if (so_luong is not None and so_luong <= 0) or (don_gia is not None and don_gia <= 0) or (so_tien is not None and so_tien <= 0):
        return {"error": "Số lượng, đơn giá, số tiền phải lớn hơn 0"}

    warnings: list[str] = []
    if so_tien is None:
        if so_luong is None or don_gia is None:
            return {"error": "Thiếu số tiền — cần so_tien, hoặc cả so_luong và don_gia để tự tính"}
        so_tien = so_luong * don_gia
    elif so_luong is not None and don_gia is not None:
        if abs(so_luong * don_gia - so_tien) / so_tien > ARITHMETIC_TOLERANCE_PCT:
            warnings.append("Số lượng × đơn giá không khớp tổng tiền — kiểm tra lại số liệu")
    if don_gia is None and so_luong is not None:
        don_gia = so_tien / so_luong

    seller = _resolve_seller_by_name(db, seller_name)
    if seller is None:
        warnings.append(f"Chưa khớp người bán nào với '{seller_name}' — chọn người bán trước khi lưu")
    else:
        warnings.append(f"Đã khớp người bán: {seller.name} — kiểm tra đúng người chưa")
        dev = price_deviation(db, seller.id, don_gia, ngay_d) if don_gia is not None else None
        if dev:
            warnings.append(
                f"Đơn giá lệch {dev['lech_pct']:+}% so với giá thường mua của người này "
                f"({dev['gia_tham_chieu']:,.0f} đ, {dev['so_mau']} phiếu gần nhất)"
            )

    return {"proposal": {
        "seller_id": str(seller.id) if seller else None,
        "seller_name": seller.name if seller else seller_name,
        "ngay": ngay_d.isoformat(),
        "ly_do_chi": ly_do_chi.strip(),
        "so_tien": so_tien,
        "so_luong": so_luong,
        "don_gia": don_gia,
        "warnings": warnings,
    }}


TOOL_HANDLERS = {
    "search_seller": lambda db, **kwargs: handle_search_seller(db, **kwargs),
    "get_monthly_summary": lambda db, **kwargs: handle_get_monthly_summary(db, **kwargs),
    "get_receivables": lambda db, **kwargs: handle_get_receivables(db, **kwargs),
    "get_price_history": lambda db, **kwargs: handle_get_price_history(db, **kwargs),
    "propose_voucher_draft": lambda db, **kwargs: handle_propose_voucher_draft(db, **kwargs),
}

