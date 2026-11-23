import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """
    Nhật ký thao tác — APPEND-ONLY. Không có API sửa/xoá bản ghi ở đây,
    và có trigger ở tầng DB chặn UPDATE/DELETE (xem migration 0001, hàm
    forbid_audit_log_mutation) — giữ đúng nguyên tắc "không ai (kể cả
    admin) sửa lại lịch sử sau khi đã ghi nhận".
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "voucher" | "seller" | "customer" | "sales_invoice" | ...
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # "create" | "update" | "approve" | "void" | "export" | ...

    # actor_id để NULL nếu hành động do Agent-BE thực hiện (agent không "đóng giả" người dùng —
    # xem actor_type để phân biệt rõ người thật vs AI đề xuất)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="user", nullable=False)  # "user" | "agent"

    before_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
