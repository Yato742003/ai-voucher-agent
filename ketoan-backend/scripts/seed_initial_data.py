"""
Chạy 1 lần sau khi migrate DB xong, để tạo sẵn 4 role và 1 tài khoản
giám đốc/admin đầu tiên (để có thể đăng nhập và tạo các user khác).

Cách chạy:
    python -m scripts.seed_initial_data
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal
from app.config import settings
from app.models.user import Role, User, RoleName
from app.core.security import hash_password


def run():
    db = SessionLocal()
    try:
        existing_roles = {r.name: r for r in db.execute(select(Role)).scalars().all()}
        for role_name in RoleName:
            if role_name.value not in existing_roles:
                role = Role(name=role_name.value)
                db.add(role)
                db.flush()
                existing_roles[role_name.value] = role
                print(f"Đã tạo role: {role_name.value}")

        admin_exists = db.execute(select(User).where(User.username == settings.initial_admin_username)).scalar_one_or_none()
        if admin_exists is None:
            admin = User(
                username=settings.initial_admin_username,
                password_hash=hash_password(settings.initial_admin_password),
                full_name="Quản trị viên",
                role_id=existing_roles[RoleName.GIAM_DOC.value].id,
                is_active=True,
            )
            db.add(admin)
            print(f"Đã tạo user admin: {settings.initial_admin_username} "
                  f"(mật khẩu: giá trị initial_admin_password trong .env — ĐỔI NGAY sau khi đăng nhập lần đầu)")
        else:
            print("User admin đã tồn tại, bỏ qua.")

        db.commit()
        print("Seed dữ liệu ban đầu hoàn tất.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
