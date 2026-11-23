import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator

from app.models.voucher import VoucherStatus


class VoucherCreate(BaseModel):
    ngay: date
    seller_id: uuid.UUID
    ly_do_chi: str
    so_tien: Decimal
    so_luong: Decimal | None = None
    don_gia: Decimal | None = None
    ghi_chu_chat_luong: str | None = None
    no_account_id: uuid.UUID | None = None
    co_account_id: uuid.UUID | None = None

    @field_validator("so_tien")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Số tiền phải lớn hơn 0")
        return v

    @field_validator("ly_do_chi")
    @classmethod
    def reason_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Lý do chi không được để trống")
        return v.strip()


class VoucherUpdate(BaseModel):
    """Chỉ cho phép sửa khi phiếu còn ở trạng thái DRAFT (áp ở tầng service)."""

    ngay: date | None = None
    seller_id: uuid.UUID | None = None
    ly_do_chi: str | None = None
    so_tien: Decimal | None = None
    so_luong: Decimal | None = None
    don_gia: Decimal | None = None
    ghi_chu_chat_luong: str | None = None
    no_account_id: uuid.UUID | None = None
    co_account_id: uuid.UUID | None = None


class VoucherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    so_phieu: str
    ngay: date
    seller_id: uuid.UUID
    ly_do_chi: str
    so_tien: Decimal
    so_luong: Decimal | None
    don_gia: Decimal | None
    ghi_chu_chat_luong: str | None
    trang_thai: VoucherStatus
    created_by: uuid.UUID
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VoucherVoidRequest(BaseModel):
    ly_do_huy: str

    @field_validator("ly_do_huy")
    @classmethod
    def reason_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Phải ghi lý do huỷ phiếu")
        return v.strip()
