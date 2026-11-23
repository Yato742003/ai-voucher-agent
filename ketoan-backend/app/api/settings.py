from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, Role, RoleName
from app.schemas.user import UserCreate, UserOut
from app.api.deps import get_current_user, require_roles
from app.services.settings_service import get_setting, set_setting
from app.core.security import hash_password

router = APIRouter(tags=["settings"])


class CompanySettings(BaseModel):
    company_name: str = ""
    company_address: str = ""
    company_tax_code: str = ""
    company_phone: str = ""


@router.get("/settings/company", response_model=CompanySettings)
def get_company_settings(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return CompanySettings(
        company_name=get_setting(db, "company_name"),
        company_address=get_setting(db, "company_address"),
        company_tax_code=get_setting(db, "company_tax_code"),
        company_phone=get_setting(db, "company_phone"),
    )


@router.put("/settings/company", response_model=CompanySettings)
def update_company_settings(
    payload: CompanySettings,
    db: Session = Depends(get_db),
    _=Depends(require_roles("giam_doc")),
):
    """Chỉ Giám đốc được sửa thông tin công ty (hiện trên mọi phiếu in ra)."""
    set_setting(db, "company_name", payload.company_name)
    set_setting(db, "company_address", payload.company_address)
    set_setting(db, "company_tax_code", payload.company_tax_code)
    set_setting(db, "company_phone", payload.company_phone)
    db.commit()
    return payload


@router.get("/users/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_roles("giam_doc"))):
    users = db.execute(select(User)).scalars().all()
    roles_by_id = {r.id: r.name for r in db.execute(select(Role)).scalars().all()}
    return [
        UserOut(id=u.id, username=u.username, full_name=u.full_name, role_name=roles_by_id.get(u.role_id, ""), is_active=u.is_active)
        for u in users
    ]


@router.post("/users/", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _=Depends(require_roles("giam_doc"))):
    """Chỉ Giám đốc được tạo tài khoản mới (VD tạo tài khoản cho kế toán/thủ quỹ)."""
    if payload.role_name not in [r.value for r in RoleName]:
        raise HTTPException(status_code=400, detail=f"role_name không hợp lệ, phải là 1 trong: {[r.value for r in RoleName]}")

    existing = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")

    role = db.execute(select(Role).where(Role.name == payload.role_name)).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=500, detail="Role chưa được seed — chạy scripts/seed_initial_data.py trước")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, username=user.username, full_name=user.full_name, role_name=role.name, is_active=user.is_active)
