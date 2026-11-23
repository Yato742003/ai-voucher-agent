import uuid
import enum
from datetime import datetime, date

from sqlalchemy import String, ForeignKey, DateTime, Date, Numeric, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SalesInvoiceStatus(str, enum.Enum):
    DRAFT = "draft"            # nháp nội bộ, chưa xuất hoá đơn thật
    ISSUED = "issued"          # đã xuất hoá đơn thật qua phần mềm HDĐT, đã nhập lại số/ký hiệu
    RECONCILED = "reconciled"  # đã đối chiếu khớp với phần mềm HDĐT / đã thu tiền


class PaymentMethod(str, enum.Enum):
    CHUYEN_KHOAN = "chuyen_khoan"
    TIEN_MAT = "tien_mat"


class SalesInvoice(Base):
    """
    Hoá đơn bán ra — CHỈ LƯU/THEO DÕI NỘI BỘ.
    Không tự phát hành hoá đơn GTGT hợp lệ pháp lý (cần phần mềm HDĐT được
    cấp phép theo Nghị định 254/2026/NĐ-CP). so_hoa_don/ky_hieu là nhập lại
    từ hoá đơn thật đã phát hành, để đối chiếu — không phải số hệ thống tự sinh.
    """

    __tablename__ = "sales_invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    so_hoa_don: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ky_hieu: Mapped[str | None] = mapped_column(String(30), nullable=True)  # VD: C26TLC
    ngay: Mapped[date] = mapped_column(Date, nullable=False)

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    ten_hang: Mapped[str] = mapped_column(String(500), nullable=False)
    so_luong: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)  # hỗ trợ số lẻ (kg)
    don_gia: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    thue_suat: Mapped[str] = mapped_column(String(20), default="KKKNT", nullable=False)  # VD KKKNT, 0%, 5%, 8%, 10%
    tong_tien: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    payment_method: Mapped[str] = mapped_column(SAEnum(PaymentMethod, name="payment_method"), default=PaymentMethod.CHUYEN_KHOAN)
    trang_thai: Mapped[str] = mapped_column(SAEnum(SalesInvoiceStatus, name="sales_invoice_status"), default=SalesInvoiceStatus.DRAFT)

    # NULL = khách chưa thanh toán (công nợ phải thu). Có giá trị = đã thu tiền.
    # Tách riêng khỏi trang_thai (trang_thai nói về việc ĐÃ XUẤT hoá đơn thật
    # hay chưa; paid_at nói về việc ĐÃ THU TIỀN hay chưa — 2 việc độc lập,
    # có thể đã xuất hoá đơn nhưng khách chưa chuyển khoản).
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="sales_invoices")
