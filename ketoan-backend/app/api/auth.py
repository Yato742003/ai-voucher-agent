import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, Role
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.user import UserOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# --- Rate limiting chống brute-force (lưu trong bộ nhớ tiến trình) ---
# Đủ dùng cho 1 tiến trình backend duy nhất (đúng quy mô "ít người dùng").
# Nếu sau này chạy nhiều tiến trình/instance song song, cần chuyển sang
# lưu chung (VD Redis) vì mỗi tiến trình sẽ có bộ đếm riêng, không dùng
# chung được nữa.
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300  # 5 phút
LOCKOUT_SECONDS = 300  # khoá thêm 5 phút sau khi vượt ngưỡng


def _check_rate_limit(key: str) -> None:
    now = time.time()
    attempts = _LOGIN_ATTEMPTS[key]
    _LOGIN_ATTEMPTS[key] = [t for t in attempts if now - t < WINDOW_SECONDS + LOCKOUT_SECONDS]
    recent_failures = [t for t in _LOGIN_ATTEMPTS[key] if now - t < WINDOW_SECONDS]
    if len(recent_failures) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Đăng nhập sai quá {MAX_ATTEMPTS} lần — vui lòng thử lại sau ít phút.",
        )


def _record_failure(key: str) -> None:
    _LOGIN_ATTEMPTS[key].append(time.time())


def _clear_failures(key: str) -> None:
    _LOGIN_ATTEMPTS.pop(key, None)


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    rate_key = form_data.username.lower().strip()
    _check_rate_limit(rate_key)

    user = db.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(form_data.password, user.password_hash):
        _record_failure(rate_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sai tên đăng nhập hoặc mật khẩu")

    _clear_failures(rate_key)
    token = create_access_token(subject=str(user.id))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.get(Role, current_user.role_id)
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        full_name=current_user.full_name,
        role_name=role.name if role else "",
        is_active=current_user.is_active,
    )


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Mật khẩu mới phải có ít nhất 8 ký tự")
        return v


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu hiện tại không đúng")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"detail": "Đã đổi mật khẩu thành công"}
