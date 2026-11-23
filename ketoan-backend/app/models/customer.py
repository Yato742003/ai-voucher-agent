import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    """Khách hàng (doanh nghiệp mua lại hàng hoá từ công ty, VD Công ty Đối tác A)."""

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    tax_code: Mapped[str | None] = mapped_column(String(30), nullable=True)  # Mã số thuế
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sales_invoices: Mapped[list["SalesInvoice"]] = relationship(back_populates="customer")
