import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def normalize_name(name: str) -> str:
    """
    Chuẩn hoá tên để so khớp trùng lặp: gộp khoảng trắng thừa, bỏ dấu,
    hạ chữ thường. Không dùng để hiển thị, chỉ dùng để so sánh/tìm trùng.
    """
    import unicodedata

    s = " ".join(name.split())
    s = s.replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return s.casefold()


class Seller(Base):
    """Người bán (chủ yếu cá nhân bán nông sản) — dùng cho Phiếu chi + Bảng kê 02/TNDN."""

    __tablename__ = "sellers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    id_card_number: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Số căn cước
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Nếu bản ghi này là 1 cách viết trùng của 1 người bán khác đã có,
    # trỏ về bản ghi "chính" thay vì xoá — giữ nguyên lịch sử phiếu cũ.
    alias_of_seller_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vouchers: Mapped[list["Voucher"]] = relationship(back_populates="seller")
