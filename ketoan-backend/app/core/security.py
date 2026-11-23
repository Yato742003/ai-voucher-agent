"""
Bảo mật: băm mật khẩu bằng bcrypt (gọi trực tiếp thư viện `bcrypt`,
KHÔNG dùng passlib — bản passlib 1.7.4 hiện không tương thích với
bcrypt>=4.1, xem: https://github.com/pyca/bcrypt/issues/684).
JWT dùng python-jose.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from app.config import settings

BCRYPT_MAX_BYTES = 72  # giới hạn cứng của thuật toán bcrypt


def hash_password(plain_password: str) -> str:
    pw_bytes = plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    hashed = bcrypt.hashpw(pw_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
