import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator

from app.models.sales_invoice import SalesInvoiceStatus, PaymentMethod


class SalesInvoiceCreate(BaseModel):
    ngay: date
    customer_id: uuid.UUID
    ten_hang: str
    so_luong: Decimal
    don_gia: Decimal
    thue_suat: str = "KKKNT"
    payment_method: PaymentMethod = PaymentMethod.CHUYEN_KHOAN
    so_hoa_don: str | None = None
    ky_hieu: str | None = None

    @field_validator("so_luong", "don_gia")
    @classmethod
    def must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Số lượng và đơn giá phải lớn hơn 0")
        return v


class SalesInvoiceMarkIssued(BaseModel):
    """Nhập lại số/ký hiệu hoá đơn THẬT đã phát hành qua phần mềm hoá đơn điện tử."""

    so_hoa_don: str
    ky_hieu: str


class SalesInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    so_hoa_don: str | None
    ky_hieu: str | None
    ngay: date
    customer_id: uuid.UUID
    ten_hang: str
    so_luong: Decimal
    don_gia: Decimal
    thue_suat: str
    tong_tien: Decimal
    payment_method: PaymentMethod
    trang_thai: SalesInvoiceStatus
    paid_at: datetime | None
    created_at: datetime
