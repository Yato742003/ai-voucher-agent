import uuid
import enum
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScanImportStatus(str, enum.Enum):
    PENDING = "pending"        # đã trích xuất, đang chờ người dùng xem/sửa
    CONFIRMED = "confirmed"    # đã xác nhận, đã tạo phiếu chi nháp
    DISCARDED = "discarded"    # người dùng huỷ, không tạo phiếu


class ScanImport(Base):
    """
    1 lượt scan bảng kê viết tay. Lưu đủ 3 thứ:
      - image_path: ảnh gốc
      - raw_extraction: JSON model trả về (chưa sửa)
      - confirmed_extraction: JSON sau khi người dùng sửa + xác nhận

    Mục đích lưu cả raw lẫn confirmed: đây chính là dữ liệu gán nhãn
    (ảnh + text đúng) để sau này fine-tune 1 model OCR riêng cho chữ viết
    tay của công ty (xem ghi chú trong app/services/scan_extraction_service.py).
    KHÔNG xoá ScanImport sau khi confirm — giữ lại làm kho dữ liệu.
    """

    __tablename__ = "scan_imports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_extraction: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confirmed_extraction: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(SAEnum(ScanImportStatus, name="scan_import_status"), default=ScanImportStatus.PENDING)
    extraction_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
