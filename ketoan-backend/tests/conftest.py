"""
Fixtures dùng chung cho test. Dùng DB Postgres RIÊNG (ketoan_test_db) —
KHÔNG đụng vào DB dev/production. Mỗi phiên chạy test: tạo sạch schema
từ đầu (Base.metadata.create_all), xoá sạch sau khi xong.

Chạy test: pytest -v  (từ thư mục gốc project, cần biến môi trường
TEST_DATABASE_URL hoặc dùng mặc định bên dưới)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/ketoan_test_db"
)

from app.database import Base, get_db  # noqa: E402
from app import models  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, Role, RoleName  # noqa: E402
from app.core.security import hash_password  # noqa: E402

engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cài đặt trigger chặn sửa/xoá audit_log giống hệt migration 0002 (autogenerate
# create_all không tự sinh trigger tuỳ biến, nên tạo lại thủ công ở đây cho
# môi trường test khớp với môi trường thật).
_AUDIT_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION forbid_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log la bang append-only: khong duoc UPDATE/DELETE ban ghi';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_forbid_audit_log_update ON audit_log;
CREATE TRIGGER trg_forbid_audit_log_update BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION forbid_audit_log_mutation();

DROP TRIGGER IF EXISTS trg_forbid_audit_log_delete ON audit_log;
CREATE TRIGGER trg_forbid_audit_log_delete BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION forbid_audit_log_mutation();
"""


@pytest.fixture(autouse=True)
def _clear_rate_limit_state():
    """
    _LOGIN_ATTEMPTS là biến toàn cục trong RAM (app/api/auth.py), KHÔNG
    nằm trong DB nên không được dọn bởi cơ chế rollback transaction của
    db_session — phải dọn tay ở đây, trước VÀ sau mỗi test, để 1 test bị
    fail giữa chừng không làm rò rỉ trạng thái khoá sang test sau.
    """
    from app.api.auth import _LOGIN_ATTEMPTS

    _LOGIN_ATTEMPTS.clear()
    yield
    _LOGIN_ATTEMPTS.clear()


@pytest.fixture(scope="session", autouse=True)
def _use_temp_upload_dir():
    import tempfile
    from app.config import settings

    with tempfile.TemporaryDirectory() as tmp:
        settings.upload_dir = tmp
        yield


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(_AUDIT_TRIGGER_SQL)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """
    1 transaction riêng cho mỗi test, ROLLBACK sau khi test xong — test
    này không ảnh hưởng dữ liệu của test khác, dù chạy trên cùng 1 DB.

    join_transaction_mode="create_savepoint": vì các API endpoint tự gọi
    db.commit() bên trong, nếu không có savepoint thì commit() đó sẽ
    commit luôn transaction ngoài — savepoint giúp commit() bên trong chỉ
    giải phóng savepoint, transaction ngoài vẫn rollback được bình thường.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_roles(db_session):
    roles = {}
    for role_name in RoleName:
        role = Role(name=role_name.value)
        db_session.add(role)
        db_session.flush()
        roles[role_name.value] = role
    db_session.commit()
    return roles


def _make_user(db_session, roles, role_name: str, username: str, password: str = "test12345") -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=f"Test {username}",
        role_id=roles[role_name].id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def giam_doc_user(db_session, seeded_roles):
    return _make_user(db_session, seeded_roles, "giam_doc", "director_test")


@pytest.fixture()
def ke_toan_user(db_session, seeded_roles):
    return _make_user(db_session, seeded_roles, "ke_toan", "accountant_test")


def auth_headers(client, username: str, password: str = "test12345") -> dict:
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
