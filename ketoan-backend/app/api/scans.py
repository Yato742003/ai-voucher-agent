import uuid
import mimetypes
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.scan_import import ScanImport, ScanImportStatus
from app.models.seller import Seller, normalize_name
from app.models.user import User
from app.schemas.scan_import import (
    ScanExtractResponse, ScanConfirmRequest, ScanConfirmResponse,
    ScanImportListItem, ScanImportDetail,
)
from app.api.deps import get_current_user
from app.services.scan_extraction_service import extract_bang_ke_from_image, validate_extracted_rows
from app.services.numbering_service import get_next_voucher_number
from app.core.audit import write_audit_log
from app.models.voucher import Voucher, VoucherStatus

router = APIRouter(prefix="/scans", tags=["scans"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _scan_to_list_item(s: ScanImport) -> ScanImportListItem:
    return ScanImportListItem(
        id=s.id,
        status=s.status.value if hasattr(s.status, "value") else s.status,
        created_at=s.created_at,
        confirmed_at=s.confirmed_at,
        so_dong_trich_xuat=len(s.raw_extraction or []),
        so_dong_xac_nhan=len(s.confirmed_extraction) if s.confirmed_extraction is not None else None,
    )


def _scan_to_detail(s: ScanImport) -> ScanImportDetail:
    return ScanImportDetail(
        id=s.id,
        status=s.status.value if hasattr(s.status, "value") else s.status,
        created_at=s.created_at,
        confirmed_at=s.confirmed_at,
        so_dong_trich_xuat=len(s.raw_extraction or []),
        so_dong_xac_nhan=len(s.confirmed_extraction) if s.confirmed_extraction is not None else None,
        raw_extraction=s.raw_extraction,
        confirmed_extraction=s.confirmed_extraction,
    )


@router.get("/", response_model=list[ScanImportListItem])
def list_scans(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Danh sách lìch sử scan, sắp giảm dần theo ngày. Dùng cho trang lịch sử.
    Không trả về raw_extraction/confirmed_extraction để tránh payload lớn.
    """
    scans = db.execute(
        select(ScanImport)
        .order_by(ScanImport.created_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    ).scalars().all()
    return [_scan_to_list_item(s) for s in scans]


@router.get("/{scan_id}", response_model=ScanImportDetail)
def get_scan_detail(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chi tiết 1 lượt scan kèm toàn bộ dữ liệu rows (raw + confirmed)."""
    scan = db.get(ScanImport, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt scan")
    return _scan_to_detail(scan)


@router.get("/{scan_id}/image")
def get_scan_image(
    scan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trả về file ảnh gốc của lượt scan (yêu cầu auth)."""
    scan = db.get(ScanImport, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt scan")
    path = Path(scan.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File ảnh không tồn tại trên server")
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=media_type or "image/jpeg")


@router.post("/extract", response_model=ScanExtractResponse)
def extract_scan(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Upload 1 ảnh bảng kê viết tay -> Claude đọc và trả về từng dòng, kèm cờ
    cảnh báo (lệch phép nhân / tên không khớp ai trong danh sách). KHÔNG
    tạo phiếu chi ở bước này — chỉ trả về để xem trước, người dùng sửa rồi
    gọi /scans/{id}/confirm mới thực sự tạo phiếu.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Định dạng file không hỗ trợ: {ext} (chỉ nhận .jpg/.png/.webp)")

    image_bytes = file.file.read()

    upload_dir = Path(settings.upload_dir) / "scan_imports"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / f"{uuid.uuid4().hex}{ext}"
    with dest_path.open("wb") as f:
        f.write(image_bytes)

    try:
        raw_rows, provider, model = extract_bang_ke_from_image(image_bytes, file.filename or "scan.jpg")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    validated_rows = validate_extracted_rows(db, raw_rows)

    scan = ScanImport(
        image_path=str(dest_path),
        raw_extraction=validated_rows,
        extraction_provider=provider,
        extraction_model=model,
        status=ScanImportStatus.PENDING,
        uploaded_by=current_user.id,
    )
    db.add(scan)
    db.flush()

    write_audit_log(
        db, entity_type="scan_import", entity_id=scan.id, action="extract",
        actor_id=current_user.id, actor_type="agent",
        after_data={"so_dong": len(validated_rows), "provider": provider, "model": model},
    )
    db.commit()

    return ScanExtractResponse(scan_id=scan.id, rows=validated_rows)


@router.post("/{scan_id}/confirm", response_model=ScanConfirmResponse)
def confirm_scan(
    scan_id: uuid.UUID,
    payload: ScanConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Xác nhận danh sách dòng (đã người dùng xem/sửa) -> tạo hàng loạt phiếu
    chi NHÁP (vẫn cần giám đốc duyệt như luồng thường). Đồng thời lưu lại
    bản đã sửa vào scan_imports.confirmed_extraction — đây là dữ liệu gán
    nhãn dùng cho việc train OCR riêng sau này.
    """
    scan = db.get(ScanImport, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt scan")
    if scan.status != ScanImportStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Lượt scan này đã ở trạng thái {scan.status}")

    created_voucher_ids = []
    for row in payload.rows:
        seller = None
        if row.seller_id:
            seller = db.get(Seller, row.seller_id)
            if seller is None:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy người bán id={row.seller_id}")
        else:
            # Tên mới hoàn toàn -> tạo người bán mới (giống hành vi khi tạo tay)
            seller = Seller(name=row.ten_nguoi_ban, name_normalized=normalize_name(row.ten_nguoi_ban))
            db.add(seller)
            db.flush()

        so_phieu = get_next_voucher_number(db, row.ngay)
        voucher = Voucher(
            so_phieu=so_phieu,
            ngay=row.ngay,
            seller_id=seller.id,
            ly_do_chi=f"Mua {row.ten_hang_hoa or 'hàng hoá'} (từ bảng kê scan)",
            so_tien=row.tong_gia_thanh_toan,
            so_luong=row.so_luong,
            don_gia=row.don_gia,
            trang_thai=VoucherStatus.DRAFT,
            created_by=current_user.id,
        )
        db.add(voucher)
        db.flush()
        created_voucher_ids.append(voucher.id)

        write_audit_log(
            db, entity_type="voucher", entity_id=voucher.id, action="create_from_scan",
            actor_id=current_user.id, after_data={"scan_id": str(scan_id)},
        )

    scan.confirmed_extraction = [row.model_dump(mode="json") for row in payload.rows]
    scan.status = ScanImportStatus.CONFIRMED
    from datetime import datetime, timezone
    scan.confirmed_at = datetime.now(timezone.utc)

    write_audit_log(
        db, entity_type="scan_import", entity_id=scan.id, action="confirm",
        actor_id=current_user.id, after_data={"so_phieu_tao": len(created_voucher_ids)},
    )
    db.commit()

    return ScanConfirmResponse(so_phieu_da_tao=len(created_voucher_ids), voucher_ids=created_voucher_ids)


@router.post("/{scan_id}/discard")
def discard_scan(scan_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    scan = db.get(ScanImport, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt scan")
    scan.status = ScanImportStatus.DISCARDED
    write_audit_log(db, entity_type="scan_import", entity_id=scan.id, action="discard", actor_id=current_user.id)
    db.commit()
    return {"detail": "Đã huỷ lượt scan này"}
