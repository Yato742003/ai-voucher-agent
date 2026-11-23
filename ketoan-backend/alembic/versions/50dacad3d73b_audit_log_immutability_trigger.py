"""audit log immutability trigger

Revision ID: 50dacad3d73b
Revises: 86dc429805f6
Create Date: 2026-07-28 05:37:31.092597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50dacad3d73b'
down_revision: Union[str, Sequence[str], None] = '86dc429805f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Chặn UPDATE/DELETE trên bảng audit_log ở tầng DB — kể cả admin/superuser
    ứng dụng cũng không sửa/xoá được bản ghi audit qua ORM, chỉ có thể INSERT.
    Muốn "sửa" lịch sử thì phải chạy tay bằng quyền DB owner, việc này nên
    hiếm và luôn để lại dấu vết ngoài quy trình bình thường.
    """
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_audit_log_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log la bang append-only: khong duoc UPDATE/DELETE ban ghi';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_forbid_audit_log_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION forbid_audit_log_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_forbid_audit_log_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION forbid_audit_log_mutation();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_forbid_audit_log_update ON audit_log;")
    op.execute("DROP TRIGGER IF EXISTS trg_forbid_audit_log_delete ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS forbid_audit_log_mutation();")
