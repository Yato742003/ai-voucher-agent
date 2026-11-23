import uuid
from datetime import datetime, date
from pydantic import BaseModel


class ExtractedRow(BaseModel):
    ten_nguoi_ban: str
    ten_hang_hoa: str | None = None
    so_luong: float
    don_gia: float
    tong_gia_thanh_toan: float
    do_tin_cay_thap: bool = False
    canh_bao_phep_nhan: bool = False
    canh_bao_ten_khong_khop: bool = False
    seller_id_goi_y: str | None = None


class ScanExtractResponse(BaseModel):
    scan_id: uuid.UUID
    rows: list[ExtractedRow]


class ConfirmedRow(BaseModel):
    ten_nguoi_ban: str
    seller_id: uuid.UUID | None = None  # nếu None, hệ thống tạo người bán mới với ten_nguoi_ban
    ten_hang_hoa: str | None = None
    so_luong: float
    don_gia: float
    tong_gia_thanh_toan: float
    ngay: date


class ScanConfirmRequest(BaseModel):
    rows: list[ConfirmedRow]


class ScanConfirmResponse(BaseModel):
    so_phieu_da_tao: int
    voucher_ids: list[uuid.UUID]


class ScanImportOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
    confirmed_at: datetime | None


class ScanImportListItem(BaseModel):
    """Dùng cho endpoint GET /scans/ — danh sách lượt scan không kèm raw data."""
    id: uuid.UUID
    status: str
    created_at: datetime
    confirmed_at: datetime | None = None
    so_dong_trich_xuat: int       # số dòng model đọc được
    so_dong_xac_nhan: int | None = None  # số dòng sau khi người dùng xác nhận


class ScanImportDetail(BaseModel):
    """Dùng cho endpoint GET /scans/{id} — kèm toàn bộ dữ liệu rows."""
    id: uuid.UUID
    status: str
    created_at: datetime
    confirmed_at: datetime | None = None
    so_dong_trich_xuat: int
    so_dong_xac_nhan: int | None = None
    raw_extraction: list | None = None         # dữ liệu model trả về (chưa sửa)
    confirmed_extraction: list | None = None   # dữ liệu sau khi người dùng sửa + xác nhận
