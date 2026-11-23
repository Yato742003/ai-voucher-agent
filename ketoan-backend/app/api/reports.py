import calendar
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.voucher import Voucher, VoucherStatus
from app.models.seller import Seller
from app.models.sales_invoice import SalesInvoice, SalesInvoiceStatus

router = APIRouter(prefix="/reports", tags=["reports"])

PENDING_SIGNATURE_WARNING_DAYS = 5  # cảnh báo nếu phiếu duyệt xong quá N ngày mà chưa có ảnh ký


class TopSeller(BaseModel):
    seller_id: str
    seller_name: str
    tong_tien: float
    tong_so_luong: float = 0.0
    so_phieu: int
    so_thang_phat_sinh: int = 1
    id_card_number: str | None = None
    phone: str | None = None
    address: str | None = None


class DashboardSummary(BaseModel):
    month: int
    year: int
    months: int = 1
    tu_thang: str = ""
    den_thang: str = ""
    tong_chi_thang_nay: float
    so_phieu_thang_nay: int
    so_phieu_cho_duyet: int
    so_phieu_cho_ky_qua_han: int
    top_nguoi_ban: list[TopSeller]
    cong_no_phai_thu: float
    so_hoa_don_cho_thu: int


@router.get("/dashboard", response_model=DashboardSummary)
def get_dashboard(
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
    months: int = Query(default=1, ge=1, le=60),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    today = date.today()
    month = month if month is not None else today.month
    year = year if year is not None else today.year

    total_end = year * 12 + (month - 1)
    total_start = total_end - (months - 1)
    start_year, start_month0 = divmod(total_start, 12)
    start_month = start_month0 + 1

    start_date = date(start_year, start_month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    month_vouchers_stmt = select(Voucher).where(
        Voucher.ngay >= start_date,
        Voucher.ngay <= end_date,
        Voucher.trang_thai != VoucherStatus.VOID,
    )
    month_vouchers = db.execute(month_vouchers_stmt).scalars().all()
    tong_chi_thang_nay = sum(float(v.so_tien) for v in month_vouchers)

    so_phieu_cho_duyet = db.execute(
        select(func.count()).select_from(Voucher).where(Voucher.trang_thai == VoucherStatus.DRAFT)
    ).scalar_one()

    warning_threshold = datetime.now(timezone.utc) - timedelta(days=PENDING_SIGNATURE_WARNING_DAYS)
    so_phieu_cho_ky_qua_han = db.execute(
        select(func.count()).select_from(Voucher).where(
            Voucher.trang_thai == VoucherStatus.PENDING_SIGNATURE,
            Voucher.approved_at < warning_threshold,
        )
    ).scalar_one()

    # Xếp hạng toàn bộ người bán trong khoảng `months` tháng theo tổng tiền giảm dần
    totals_by_seller: dict = {}
    for v in month_vouchers:
        entry = totals_by_seller.setdefault(
            v.seller_id,
            {"tong_tien": 0.0, "tong_so_luong": 0.0, "so_phieu": 0, "active_months": set()},
        )
        entry["tong_tien"] += float(v.so_tien)
        entry["tong_so_luong"] += float(v.so_luong) if v.so_luong is not None else 0.0
        entry["so_phieu"] += 1
        entry["active_months"].add((v.ngay.year, v.ngay.month))

    ranked_ids = sorted(totals_by_seller.items(), key=lambda kv: kv[1]["tong_tien"], reverse=True)
    top_nguoi_ban = []
    for seller_id, stats in ranked_ids:
        seller = db.get(Seller, seller_id)
        top_nguoi_ban.append(
            TopSeller(
                seller_id=str(seller_id),
                seller_name=seller.name if seller else "(không rõ)",
                tong_tien=stats["tong_tien"],
                tong_so_luong=round(stats["tong_so_luong"], 3),
                so_phieu=stats["so_phieu"],
                so_thang_phat_sinh=len(stats["active_months"]),
                id_card_number=seller.id_card_number if seller else None,
                phone=seller.phone if seller else None,
                address=seller.address if seller else None,
            )
        )

    unpaid_stmt = select(SalesInvoice).where(
        SalesInvoice.trang_thai == SalesInvoiceStatus.ISSUED,
        SalesInvoice.paid_at.is_(None),
    )
    unpaid_invoices = db.execute(unpaid_stmt).scalars().all()
    cong_no_phai_thu = sum(float(inv.tong_tien) for inv in unpaid_invoices)

    return DashboardSummary(
        month=month,
        year=year,
        months=months,
        tu_thang=f"{start_month:02d}/{start_year}",
        den_thang=f"{month:02d}/{year}",
        tong_chi_thang_nay=tong_chi_thang_nay,
        so_phieu_thang_nay=len(month_vouchers),
        so_phieu_cho_duyet=so_phieu_cho_duyet,
        so_phieu_cho_ky_qua_han=so_phieu_cho_ky_qua_han,
        top_nguoi_ban=top_nguoi_ban,
        cong_no_phai_thu=cong_no_phai_thu,
        so_hoa_don_cho_thu=len(unpaid_invoices),
    )
