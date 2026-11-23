import uuid
import enum
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AttachmentType(str, enum.Enum):
    SIGNED_SCAN = "signed_scan"  # ảnh/scan phiếu đã có chữ ký người bán
    OTHER = "other"


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    voucher_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vouchers.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    loai: Mapped[str] = mapped_column(SAEnum(AttachmentType, name="attachment_type"), default=AttachmentType.SIGNED_SCAN)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    voucher: Mapped["Voucher"] = relationship(back_populates="attachments")
