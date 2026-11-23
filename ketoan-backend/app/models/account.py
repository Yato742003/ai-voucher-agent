import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Account(Base):
    """Tài khoản kế toán (chart of accounts) — dùng cho Nợ/Có trên phiếu chi."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # VD: "1111", "3311"
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class SequenceCounter(Base):
    """
    Bộ đếm cấp số phiếu tự động theo tháng/năm — tránh trùng/nhảy số.
    Dùng SELECT ... FOR UPDATE khi cấp số mới (xem app/services/numbering_service.py)
    để an toàn khi có nhiều người tạo phiếu cùng lúc.
    """

    __tablename__ = "sequence_counters"
    __table_args__ = (UniqueConstraint("prefix", "year", "month", name="uq_sequence_prefix_year_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)  # VD: "PC" cho phiếu chi
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
