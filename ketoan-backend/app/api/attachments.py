import uuid
import shutil
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.voucher import Voucher, VoucherStatus
from app.models.attachment import Attachment, AttachmentType
from app.models.user import User
from app.api.deps import get_current_user
from app.core.audit import write_audit_log

router = APIRouter(prefix="/vouchers", tags=["attachments"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".webp"}


@router.post("/{voucher_id}/signed-scan", status_code=status.HTTP_201_CREATED)
def upload_signed_scan(
    voucher_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload ảnh/scan phiếu đã có chữ ký người bán. Chỉ nhận khi phiếu đang
    ở trạng thái PENDING_SIGNATURE (đã duyệt, đã in, đang chờ ký) — nếu
    phiếu còn DRAFT nghĩa là chưa qua bước duyệt, chưa nên có ảnh ký.
    Upload thành công sẽ tự chuyển phiếu sang SIGNED.
    """
    voucher = db.get(Voucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu chi")
    if voucher.trang_thai != VoucherStatus.PENDING_SIGNATURE:
        raise HTTPException(
            status_code=409,
            detail=f"Phiếu phải ở trạng thái 'chờ ký' mới nhận ảnh đã ký (hiện tại: {voucher.trang_thai.value})",
        )

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Định dạng file không hỗ trợ: {ext}")

    upload_dir = Path(settings.upload_dir) / "signed_scans"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / f"{voucher.so_phieu.replace('/', '-')}_{uuid.uuid4().hex[:8]}{ext}"

    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    attachment = Attachment(
        voucher_id=voucher.id,
        file_path=str(dest_path),
        loai=AttachmentType.SIGNED_SCAN,
        uploaded_by=current_user.id,
    )
    db.add(attachment)

    voucher.trang_thai = VoucherStatus.SIGNED

    write_audit_log(
        db, entity_type="voucher", entity_id=voucher.id, action="upload_signed_scan",
        actor_id=current_user.id, after_data={"trang_thai": "signed", "file": str(dest_path)},
    )
    db.commit()

    return {"attachment_id": str(attachment.id), "voucher_status": voucher.trang_thai.value}


@router.get("/{voucher_id}/signed-scan")
def download_signed_scan(
    voucher_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Xem/Tải ảnh scan phiếu chi đã ký.
    """
    attachment = db.query(Attachment).filter(
        Attachment.voucher_id == voucher_id,
        Attachment.loai == AttachmentType.SIGNED_SCAN
    ).first()

    if attachment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh quét đã ký cho phiếu chi này")

    path = Path(attachment.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File không tồn tại trên hệ thống lưu trữ")

    suffix = path.suffix.lower()
    if suffix in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif suffix == ".png":
        media_type = "image/png"
    elif suffix == ".pdf":
        media_type = "application/pdf"
    elif suffix == ".webp":
        media_type = "image/webp"
    else:
        media_type = "application/octet-stream"

    return FileResponse(path=str(path), media_type=media_type, filename=path.name)
