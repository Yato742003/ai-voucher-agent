from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # trả nguyên lại từ response trước để giữ ngữ cảnh nhiều lượt (text thuần)
    context: str | None = None  # trang người dùng đang mở (VD "/vouchers") — để agent hiểu "ở đây" là đâu


class VoucherProposal(BaseModel):
    """Thẻ đề xuất phiếu chi nháp. KHÔNG phải phiếu thật — chỉ lưu khi người dùng bấm xác nhận."""

    seller_id: str | None
    seller_name: str
    ngay: str
    ly_do_chi: str
    so_tien: float
    so_luong: float | None = None
    don_gia: float | None = None
    warnings: list[str] = []


class AgentChatResponse(BaseModel):
    reply: str
    history: list[dict]
    tool_calls_made: list[str]
    proposals: list[VoucherProposal] = []


class AgentAlert(BaseModel):
    type: str
    severity: str  # "warn" | "alert"
    title: str
    detail: str
    link: str
