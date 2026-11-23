import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy import select, extract
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.voucher import Voucher, VoucherStatus
from app.models.seller import Seller
from app.models.user import User, Role
from app.schemas.voucher import VoucherCreate, VoucherUpdate, VoucherOut, VoucherVoidRequest
from app.api.deps import get_current_user, require_roles
from app.services.numbering_service import get_next_voucher_number
from app.core.audit import write_audit_log

router = APIRouter(prefix="/vouchers", tags=["vouchers"])


@router.get("/", response_model=list[VoucherOut])
def list_vouchers(
    seller_id: uuid.UUID | None = None,
    month: int | None = None,
    year: int | None = None,
    trang_thai: VoucherStatus | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Voucher)
    if seller_id:
        stmt = stmt.where(Voucher.seller_id == seller_id)
    if month:
        stmt = stmt.where(extract("month", Voucher.ngay) == month)
    if year:
        stmt = stmt.where(extract("year", Voucher.ngay) == year)
    if trang_thai:
        stmt = stmt.where(Voucher.trang_thai == trang_thai)
    return db.execute(stmt.order_by(Voucher.ngay.desc(), Voucher.so_phieu.desc())).scalars().all()


@router.get("/{voucher_id}", response_model=VoucherOut)
def get_voucher(voucher_id: uuid.UUID, db: Session = Depends(get_db), _=Depends(get_current_user)):
    voucher = db.get(Voucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu chi")
    return voucher


@router.post("/", response_model=VoucherOut, status_code=status.HTTP_201_CREATED)
def create_voucher(payload: VoucherCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = db.get(Seller, payload.seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người bán — hãy tạo người bán trước")

    so_phieu = get_next_voucher_number(db, payload.ngay)

    voucher = Voucher(
        so_phieu=so_phieu,
        ngay=payload.ngay,
        seller_id=payload.seller_id,
        ly_do_chi=payload.ly_do_chi,
        so_tien=payload.so_tien,
        so_luong=payload.so_luong,
        don_gia=payload.don_gia,
        ghi_chu_chat_luong=payload.ghi_chu_chat_luong,
        no_account_id=payload.no_account_id,
        co_account_id=payload.co_account_id,
        trang_thai=VoucherStatus.DRAFT,
        created_by=current_user.id,
    )
    db.add(voucher)
    db.flush()

    write_audit_log(
        db, entity_type="voucher", entity_id=voucher.id, action="create",
        actor_id=current_user.id, after_data=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(voucher)
    return voucher


@router.patch("/{voucher_id}", response_model=VoucherOut)
def update_voucher(voucher_id: uuid.UUID, payload: VoucherUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    voucher = db.get(Voucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu chi")
    if voucher.trang_thai != VoucherStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chỉ sửa được phiếu ở trạng thái nháp (hiện tại: {voucher.trang_thai.value}). "
                   f"Muốn điều chỉnh, hãy tạo phiếu mới và ghi chú tham chiếu.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    before = {k: getattr(voucher, k) for k in update_data}
    for field, value in update_data.items():
        setattr(voucher, field, value)

    write_audit_log(
        db, entity_type="voucher", entity_id=voucher.id, action="update",
        actor_id=current_user.id, before_data=_jsonable(before), after_data=_jsonable(update_data),
    )
    db.commit()
    db.refresh(voucher)
    return voucher


@router.post("/{voucher_id}/approve", response_model=VoucherOut)
def approve_voucher(
    voucher_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("giam_doc")),
):
    """Chỉ Giám đốc được duyệt — chuyển DRAFT -> PENDING_SIGNATURE (sẵn sàng in & đưa người bán ký)."""
    from datetime import datetime, timezone

    voucher = db.get(Voucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu chi")
    if voucher.trang_thai != VoucherStatus.DRAFT:
        raise HTTPException(status_code=409, detail=f"Phiếu đang ở trạng thái {voucher.trang_thai.value}, không thể duyệt")

    voucher.trang_thai = VoucherStatus.PENDING_SIGNATURE
    voucher.approved_by = current_user.id
    voucher.approved_at = datetime.now(timezone.utc)

    write_audit_log(
        db, entity_type="voucher", entity_id=voucher.id, action="approve",
        actor_id=current_user.id, after_data={"trang_thai": voucher.trang_thai.value},
    )
    db.commit()
    db.refresh(voucher)
    return voucher


@router.post("/{voucher_id}/void", response_model=VoucherOut)
def void_voucher(
    voucher_id: uuid.UUID,
    payload: VoucherVoidRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("giam_doc")),
):
    """
    Huỷ phiếu — KHÔNG xoá bản ghi (giữ nguyên để không bị nhảy số / mất dấu vết).
    Chỉ Giám đốc được huỷ, và bắt buộc phải ghi lý do (đi vào audit_log).
    """
    voucher = db.get(Voucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu chi")
    if voucher.trang_thai == VoucherStatus.VOID:
        raise HTTPException(status_code=409, detail="Phiếu đã bị huỷ trước đó")

    before_status = voucher.trang_thai.value
    voucher.trang_thai = VoucherStatus.VOID

    write_audit_log(
        db, entity_type="voucher", entity_id=voucher.id, action="void",
        actor_id=current_user.id,
        before_data={"trang_thai": before_status},
        after_data={"trang_thai": "void", "ly_do_huy": payload.ly_do_huy},
    )
    db.commit()
    db.refresh(voucher)
    return voucher


@router.delete("/{voucher_id}", status_code=status.HTTP_200_OK)
def delete_voucher(
    voucher_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("giam_doc", "ke_toan")),
):
    """
    Xoá phiếu chi.
    - Kế toán chỉ được xoá phiếu ở trạng thái DRAFT (nháp).
    - Giám đốc được quyền xoá phiếu ở bất kỳ trạng thái nào.
    Ghi nhận audit log trước khi xoá khỏi database.
    """
    voucher = db.get(Voucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu chi")

    role = db.get(Role, current_user.role_id)
    is_giam_doc = role is not None and role.name == "giam_doc"
    if voucher.trang_thai != VoucherStatus.DRAFT and not is_giam_doc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Kế toán chỉ được xoá phiếu ở trạng thái nháp. Phiếu đang ở trạng thái {voucher.trang_thai.value}.",
        )

    before_data = _jsonable({
        "so_phieu": voucher.so_phieu,
        "ngay": voucher.ngay,
        "seller_id": voucher.seller_id,
        "so_tien": voucher.so_tien,
        "trang_thai": voucher.trang_thai.value,
    })

    write_audit_log(
        db, entity_type="voucher", entity_id=voucher.id, action="delete",
        actor_id=current_user.id, before_data=before_data, after_data={"deleted": True},
    )

    db.delete(voucher)
    db.commit()

    return {"message": "Đã xoá phiếu chi thành công", "id": str(voucher_id)}



def _jsonable(d: dict) -> dict:
    """Chuyển các kiểu không phải JSON thuần (date, Decimal, UUID...) sang string để lưu vào JSONB."""
    out = {}
    for k, v in d.items():
        if isinstance(v, (date,)):
            out[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            out[k] = str(v)
        else:
            try:
                out[k] = float(v) if hasattr(v, "__float__") and not isinstance(v, (int, float, str, bool)) else v
            except (TypeError, ValueError):
                out[k] = str(v)
    return out


@router.post("/import-excel", status_code=status.HTTP_200_OK)
def import_vouchers_from_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("giam_doc", "ke_toan")),
):
    """
    Import phiếu chi từ file Excel tải lên.
    """
    import os
    import shutil
    import tempfile
    from pathlib import Path
    from app.migration.import_from_excel import import_file

    # Verify file extension
    suffix = Path(file.filename or "import.xlsx").suffix.lower()
    if suffix not in [".xlsx", ".xlsm"]:
        raise HTTPException(
            status_code=400,
            detail="Định dạng file không hợp lệ. Chỉ chấp nhận file Excel (.xlsx, .xlsm)"
        )

    # Save to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Run import_file from import_from_excel.py
        stats = import_file(
            xlsx_path=tmp_path,
            created_by_username=current_user.username,
            dry_run=False,
            force=True, # Allow importing even if marked imported, since the user explicitly uploaded it!
            db_session=db,
        )
        stats["file"] = file.filename
        return stats
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi xử lý file: {str(e)}")
    finally:
        # Cleanup temporary file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
