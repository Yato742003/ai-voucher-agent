from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app.database import get_db
from app.api.deps import get_current_user
from app.services.export_service import export_grouped_by_seller, export_bang_ke_02_tndn
from app.core.audit import write_audit_log
from app.models.user import User
import uuid

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/grouped-by-seller")
def export_grouped(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Xuất file Excel gồm toàn bộ phiếu chi hợp lệ trong tháng/năm chỉ định,
    gom nhóm theo người bán, sẵn sàng in để mang đi ký — thay thế bước
    làm thủ công cuối tháng.
    """
    try:
        file_bytes = export_grouped_by_seller(db, month, year)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Lỗi kiểm tra quy chuẩn gom nhóm (gom_nhom_phieu_chi.py): {e}"
        )

    write_audit_log(
        db, entity_type="export", entity_id=uuid.uuid4(), action="export_grouped_by_seller",
        actor_id=current_user.id, after_data={"month": month, "year": year},
    )
    db.commit()

    filename = f"PhieuChi_gom_nhom_{month:02d}_{year}.xlsx"
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/bang-ke-02-tndn")
def export_bang_ke(month: int, year: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Xuất Bảng kê 02/TNDN (Thông tư 20/2026/TT-BTC) cho kỳ chỉ định — hợp
    thức hoá chi phí mua hàng không hoá đơn khi tính thuế TNDN. Vẫn cần
    kế toán rà lại trước khi nộp — hệ thống chỉ hỗ trợ soạn sẵn.
    """
    file_bytes = export_bang_ke_02_tndn(db, month, year)

    write_audit_log(
        db, entity_type="export", entity_id=uuid.uuid4(), action="export_bang_ke_02_tndn",
        actor_id=current_user.id, after_data={"month": month, "year": year},
    )
    db.commit()

    filename = f"BangKe_02TNDN_{month:02d}_{year}.xlsx"
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
