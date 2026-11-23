"""
Giám sát chủ động (ambient): quét dữ liệu thật và trả về danh sách cảnh báo.

Cố ý KHÔNG dùng LLM ở đây — quy tắc xác định thì rẻ, lặp lại được, không bịa.
Mọi ngưỡng là hằng số ở đầu file (nguồn duy nhất, không rải ở nơi khác).
`price_deviation` cũng được tool `propose_voucher_draft` dùng lại để cảnh báo
ngay lúc đề xuất phiếu.
"""
import uuid
from datetime import date, timedelta
from statistics import median

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.voucher import Voucher, VoucherStatus
from app.models.seller import Seller
from app.models.sales_invoice import SalesInvoice, SalesInvoiceStatus

PRICE_HISTORY_DAYS = 90      # cửa sổ lịch sử giá để lấy giá tham chiếu
PRICE_MIN_SAMPLES = 3        # ít hơn số phiếu này thì không đủ cơ sở để kết luận "bất thường"
PRICE_DEVIATION_PCT = 0.20   # lệch quá 20% so với trung vị thì cảnh báo
PRICE_SCAN_DAYS = 30         # chỉ quét các phiếu trong 30 ngày gần nhất
RECEIVABLE_OVERDUE_DAYS = 30
CONTRACT_WINDOW_DAYS = 90
CONTRACT_TOP_SELLERS = 10    # top N người bán theo doanh số cần có đủ CCCD để ký hợp đồng


def _vnd(n: float) -> str:
    return f"{n:,.0f}".replace(",", ".")


def price_deviation(
    db: Session,
    seller_id: uuid.UUID,
    don_gia: float,
    ref_date: date,
    exclude_voucher_id: uuid.UUID | None = None,
) -> dict | None:
    """
    So `don_gia` với trung vị đơn giá các phiếu gần đây của CHÍNH người bán đó.
    Trả None nếu bình thường hoặc không đủ dữ liệu (< PRICE_MIN_SAMPLES phiếu).
    ponytail: chưa tách theo mặt hàng — người bán bán nhiều loại giá khác nhau có
    thể bị báo nhầm; thêm nhóm theo mặt hàng khi có cột mặt hàng riêng trên phiếu.
    """
    stmt = select(Voucher.don_gia).where(
        Voucher.seller_id == seller_id,
        Voucher.don_gia.is_not(None),
        Voucher.trang_thai != VoucherStatus.VOID,
        Voucher.ngay >= ref_date - timedelta(days=PRICE_HISTORY_DAYS),
        Voucher.ngay <= ref_date,
    )
    if exclude_voucher_id is not None:
        stmt = stmt.where(Voucher.id != exclude_voucher_id)
    prices = [float(p) for p in db.execute(stmt).scalars().all()]
    if len(prices) < PRICE_MIN_SAMPLES:
        return None
    ref = median(prices)
    if ref <= 0:
        return None
    pct = (float(don_gia) - ref) / ref
    if abs(pct) <= PRICE_DEVIATION_PCT:
        return None
    return {"gia_tham_chieu": ref, "lech_pct": round(pct * 100, 1), "so_mau": len(prices)}


def find_alerts(db: Session, today: date | None = None) -> list[dict]:
    """`today` cho phép tiêm đồng hồ khi test (không phụ thuộc ngày chạy thật)."""
    today = today or date.today()
    alerts: list[dict] = []

    # 1. Công nợ phải thu quá hạn
    cutoff = today - timedelta(days=RECEIVABLE_OVERDUE_DAYS)
    overdue = db.execute(
        select(SalesInvoice).where(
            SalesInvoice.trang_thai == SalesInvoiceStatus.ISSUED,
            SalesInvoice.paid_at.is_(None),
            SalesInvoice.ngay < cutoff,
        )
    ).scalars().all()
    if overdue:
        total = sum(float(i.tong_tien) for i in overdue)
        alerts.append({
            "type": "receivable_overdue", "severity": "alert",
            "title": f"{len(overdue)} hoá đơn đã xuất quá {RECEIVABLE_OVERDUE_DAYS} ngày chưa thu tiền",
            "detail": f"Tổng công nợ quá hạn: {_vnd(total)} đ",
            "link": "/sales-invoices",
        })

    # 2. Đơn giá thu mua lệch bất thường
    recent = db.execute(
        select(Voucher).where(
            Voucher.don_gia.is_not(None),
            Voucher.trang_thai != VoucherStatus.VOID,
            Voucher.ngay >= today - timedelta(days=PRICE_SCAN_DAYS),
            Voucher.ngay <= today,
        ).order_by(Voucher.ngay.desc())
    ).scalars().all()
    for v in recent:
        dev = price_deviation(db, v.seller_id, v.don_gia, v.ngay, exclude_voucher_id=v.id)
        if dev:
            seller = db.get(Seller, v.seller_id)
            name = seller.name if seller else "(không rõ)"
            alerts.append({
                "type": "price_anomaly", "severity": "warn",
                "title": f"Phiếu {v.so_phieu}: đơn giá lệch {dev['lech_pct']:+}% so với giá thường mua của {name}",
                "detail": f"Đơn giá {_vnd(float(v.don_gia))} đ, giá tham chiếu {_vnd(dev['gia_tham_chieu'])} đ ({dev['so_mau']} phiếu gần nhất)",
                "link": "/vouchers",
            })

    # 3. Người bán doanh số cao nhưng thiếu CCCD (cần để ký hợp đồng)
    rows = db.execute(
        select(Voucher.seller_id)
        .where(
            Voucher.trang_thai != VoucherStatus.VOID,
            Voucher.ngay >= today - timedelta(days=CONTRACT_WINDOW_DAYS),
            Voucher.ngay <= today,
        )
        .group_by(Voucher.seller_id)
        .order_by(func.sum(Voucher.so_tien).desc())
        .limit(CONTRACT_TOP_SELLERS)
    ).scalars().all()
    missing = []
    for seller_id in rows:
        seller = db.get(Seller, seller_id)
        if seller and not (seller.id_card_number or "").strip():
            missing.append(seller.name)
    if missing:
        alerts.append({
            "type": "seller_missing_id", "severity": "warn",
            "title": f"{len(missing)} người bán top {CONTRACT_TOP_SELLERS} ({CONTRACT_WINDOW_DAYS} ngày) chưa có CCCD",
            "detail": ", ".join(missing),
            "link": "/sellers",
        })

    return alerts
