import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class SellerBase(BaseModel):
    name: str
    address: str | None = None
    id_card_number: str | None = None
    phone: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Tên người bán không được để trống")
        return v.strip()


class SellerCreate(SellerBase):
    pass


class SellerUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    id_card_number: str | None = None
    phone: str | None = None


class SellerOut(SellerBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alias_of_seller_id: uuid.UUID | None = None
    created_at: datetime


class SellerDuplicateCandidate(BaseModel):
    """Kết quả cảnh báo trùng khi tạo người bán mới."""

    seller: SellerOut
    similarity_score: float  # 0-100, càng cao càng giống
