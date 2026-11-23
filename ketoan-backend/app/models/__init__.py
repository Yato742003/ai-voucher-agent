"""
Import tất cả model ở đây — bắt buộc để Alembic autogenerate (env.py)
nhìn thấy đủ bảng khi tạo migration mới, và để SQLAlchemy resolve được
các quan hệ (relationship) tham chiếu chéo giữa các file model.
"""
from app.models.user import Role, User, RoleName  # noqa: F401
from app.models.seller import Seller  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.voucher import Voucher, VoucherStatus  # noqa: F401
from app.models.sales_invoice import SalesInvoice, SalesInvoiceStatus, PaymentMethod  # noqa: F401
from app.models.attachment import Attachment, AttachmentType  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.account import Account, SequenceCounter  # noqa: F401
from app.models.setting import AppSetting  # noqa: F401
from app.models.scan_import import ScanImport, ScanImportStatus  # noqa: F401
