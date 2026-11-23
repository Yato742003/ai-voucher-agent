import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không xác thực được — vui lòng đăng nhập lại",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_error

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise credentials_error

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_roles(*allowed_role_names: str):
    """
    Dùng làm dependency: Depends(require_roles("giam_doc"))
    Chặn ở tầng API — ngay cả khi Agent-BE gọi cùng endpoint này cũng
    chịu đúng luật phân quyền như người dùng thật.
    """

    def _checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        role = db.get(Role, current_user.role_id)
        if role is None or role.name not in allowed_role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Chức năng này yêu cầu quyền: {', '.join(allowed_role_names)}",
            )
        return current_user

    return _checker
