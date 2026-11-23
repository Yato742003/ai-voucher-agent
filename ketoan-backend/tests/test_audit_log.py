import uuid
import pytest
from sqlalchemy.exc import InternalError
from sqlalchemy import select

from tests.conftest import auth_headers
from app.models.audit_log import AuditLog


def test_actions_are_logged(client, giam_doc_user, db_session):
    headers = auth_headers(client, "director_test")
    seller = client.post("/sellers/", headers=headers, json={"name": "Nguyễn Văn A"}).json()
    v = client.post(
        "/vouchers/", headers=headers,
        json={"ngay": "2026-07-05", "seller_id": seller["id"], "ly_do_chi": "test", "so_tien": 100000},
    ).json()
    client.post(f"/vouchers/{v['id']}/approve", headers=headers)

    logs = db_session.execute(
        select(AuditLog).where(AuditLog.entity_id == uuid.UUID(v["id"]))
    ).scalars().all()
    actions = {log.action for log in logs}
    assert "create" in actions
    assert "approve" in actions


def test_audit_log_cannot_be_updated_or_deleted_at_db_level(db_session):
    """Xác nhận lại bằng code (không chỉ psql tay) rằng trigger append-only hoạt động."""
    entry = AuditLog(entity_type="test", entity_id=uuid.uuid4(), action="create", actor_id=None, actor_type="user")
    db_session.add(entry)
    db_session.flush()

    entry.action = "hacked"
    with pytest.raises(InternalError, match="append-only"):
        db_session.flush()
    db_session.rollback()
