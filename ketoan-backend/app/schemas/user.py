import uuid
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: str
    role_name: str
    is_active: bool


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role_name: str  # "giam_doc" | "ke_toan" | "thu_quy" | "nhan_vien"
