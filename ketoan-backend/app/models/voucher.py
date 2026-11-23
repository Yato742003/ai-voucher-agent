import uuid
import enum
from datetime import datetime, date

from sqlalchemy import String, ForeignKey, DateTime, Date, Numeric, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VoucherStatus(str, enum.Enum):
    DRAFT = "draft"                        # vừa tạo, có thể sửa tự do
    PENDING_SIGNATURE = "pending_signature"  # giám đốc đã duyệt, chờ in & người bán ký
    SIGNED = "signed"                      # đã có ảnh scan phiếu ký, coi như hoàn tất
    ARCHIVED = "archived"                  # đã đưa vào kỳ báo cáo/lưu trữ, không sửa được nữa
    VOID = "void"                          # huỷ (không xoá — giữ lại để không bị nhảy số)


class Voucher(Base):
    """Phiếu chi (Mẫu 02-TT) — trả tiền mặt cho người bán."""

    __tablename__ = "vouchers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    so_phieu: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    ngay: Mapped[date] = mapped_column(Date, nullable=False)

    seller_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=False)
    ly_do_chi: Mapped[str] = mapped_column(String(500), nullable=False)
    so_tien: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    # Tuỳ chọn — chỉ cần điền khi muốn xuất Bảng kê 02/TNDN đầy đủ cột
    # "Số lượng/Trọng lượng" và "Đơn giá". so_tien vẫn là số tiền THẬT trả
    # (nguồn xác thực cho phiếu chi), 2 trường này chỉ để bổ sung chi tiết,
    # không bắt buộc phải khớp phép nhân nếu có làm tròn/phụ phí.
    so_luong: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    don_gia: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)

    # Tuỳ chọn — ghi chú chất lượng khi cân hàng (độ ẩm, tạp chất, trọng
    # lượng xe...) nếu công ty có đo. Để dạng text tự do vì mỗi nơi có
    # thể ghi khác nhau; KHÔNG tự tính trừ hao vào so_tien/so_luong —
    # con số cuối vẫn do người nhập quyết định, đây chỉ là ghi chú lưu
    # lại để đối chiếu sau này.
    ghi_chu_chat_luong: Mapped[str | None] = mapped_column(String(500), nullable=True)

    no_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)
    co_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True)

    trang_thai: Mapped[str] = mapped_column(SAEnum(VoucherStatus, name="voucher_status"), default=VoucherStatus.DRAFT, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    seller: Mapped["Seller"] = relationship(back_populates="vouchers")
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="voucher", cascade="all, delete-orphan")

    # Nguyên tắc kiểm soát: mọi sửa đổi SAU KHI đã pending_signature trở đi nên bị chặn
    # ở tầng service (app/services), không sửa đè — muốn điều chỉnh thì tạo phiếu mới
    # và ghi chú tham chiếu, giữ đúng tinh thần chứng từ kế toán không sửa sau khi phát hành.
