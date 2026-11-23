import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sales_invoice import SalesInvoice, SalesInvoiceStatus
from app.models.customer import Customer
from app.models.user import User
from app.schemas.sales_invoice import SalesInvoiceCreate, SalesInvoiceMarkIssued, SalesInvoiceOut
from app.api.deps import get_current_user
from app.core.audit import write_audit_log

router = APIRouter(prefix="/sales-invoices", tags=["sales_invoices"])


@router.get("/", response_model=list[SalesInvoiceOut])
def list_sales_invoices(customer_id: uuid.UUID | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(SalesInvoice)
    if customer_id:
        stmt = stmt.where(SalesInvoice.customer_id == customer_id)
    return db.execute(stmt.order_by(SalesInvoice.ngay.desc())).scalars().all()


@router.post("/", response_model=SalesInvoiceOut, status_code=status.HTTP_201_CREATED)
def create_sales_invoice(payload: SalesInvoiceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    customer = db.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng — hãy tạo khách hàng trước")

    tong_tien = payload.so_luong * payload.don_gia
    invoice = SalesInvoice(
        so_hoa_don=payload.so_hoa_don,
        ky_hieu=payload.ky_hieu,
        ngay=payload.ngay,
        customer_id=payload.customer_id,
        ten_hang=payload.ten_hang,
        so_luong=payload.so_luong,
        don_gia=payload.don_gia,
        thue_suat=payload.thue_suat,
        tong_tien=tong_tien,
        payment_method=payload.payment_method,
        trang_thai=SalesInvoiceStatus.ISSUED if payload.so_hoa_don else SalesInvoiceStatus.DRAFT,
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    write_audit_log(
        db, entity_type="sales_invoice", entity_id=invoice.id, action="create",
        actor_id=current_user.id, after_data=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/mark-issued", response_model=SalesInvoiceOut)
def mark_issued(invoice_id: uuid.UUID, payload: SalesInvoiceMarkIssued, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Nhập lại số/ký hiệu hoá đơn THẬT đã phát hành qua phần mềm hoá đơn điện tử, để đối chiếu."""
    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hoá đơn")

    invoice.so_hoa_don = payload.so_hoa_don
    invoice.ky_hieu = payload.ky_hieu
    invoice.trang_thai = SalesInvoiceStatus.ISSUED

    write_audit_log(
        db, entity_type="sales_invoice", entity_id=invoice.id, action="mark_issued",
        actor_id=current_user.id, after_data=payload.model_dump(),
    )
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/mark-paid", response_model=SalesInvoiceOut)
def mark_paid(invoice_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Đánh dấu đã thu tiền — dùng cho theo dõi công nợ phải thu ở dashboard."""
    from datetime import datetime, timezone

    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hoá đơn")
    if invoice.paid_at is not None:
        raise HTTPException(status_code=409, detail="Hoá đơn này đã được đánh dấu thu tiền trước đó")

    invoice.paid_at = datetime.now(timezone.utc)
    write_audit_log(
        db, entity_type="sales_invoice", entity_id=invoice.id, action="mark_paid",
        actor_id=current_user.id, after_data={"paid_at": invoice.paid_at.isoformat()},
    )
    db.commit()
    db.refresh(invoice)
    return invoice
