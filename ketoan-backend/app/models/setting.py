from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSetting(Base):
    """
    Bảng cấu hình key-value đơn giản — dùng cho thông tin công ty
    (tên, địa chỉ, mã số thuế) hiển thị khi in phiếu, và các cấu hình
    khác về sau mà không cần thêm bảng/migration mới mỗi lần.

    Các key gợi ý cho thông tin công ty:
      company_name, company_address, company_tax_code, company_phone
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
