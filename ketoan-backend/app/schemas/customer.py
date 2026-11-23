import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class CustomerBase(BaseModel):
    company_name: str
    tax_code: str | None = None
    address: str | None = None
    contact_phone: str | None = None
    bank_account: str | None = None

    @field_validator("company_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Tên khách hàng không được để trống")
        return v.strip()


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    company_name: str | None = None
    tax_code: str | None = None
    address: str | None = None
    contact_phone: str | None = None
    bank_account: str | None = None


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
