"""
Helper ghi audit log. Luôn gọi hàm này trong CÙNG transaction với thao tác
nghiệp vụ (không tự commit ở đây) — để nếu thao tác chính rollback thì log
cũng rollback theo, tránh log "ma" cho hành động không thực sự xảy ra.
"""
import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor_id: uuid.UUID | None,
    actor_type: str = "user",
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_type=actor_type,
        before_data=before_data,
        after_data=after_data,
    )
    db.add(entry)
    db.flush()  # để có entry.id nếu caller cần, nhưng chưa commit
    return entry
