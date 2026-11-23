import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.seller import Seller, normalize_name
from app.models.user import User
from app.schemas.seller import SellerCreate, SellerUpdate, SellerOut, SellerDuplicateCandidate
from app.api.deps import get_current_user
from app.services.fuzzy_match_service import find_possible_duplicates
from app.core.audit import write_audit_log

router = APIRouter(prefix="/sellers", tags=["sellers"])


@router.get("/", response_model=list[SellerOut])
def list_sellers(q: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(Seller).where(Seller.alias_of_seller_id.is_(None))
    if q:
        stmt = stmt.where(Seller.name.ilike(f"%{q}%"))
    return db.execute(stmt.order_by(Seller.name)).scalars().all()


@router.get("/check-duplicate", response_model=list[SellerDuplicateCandidate])
def check_duplicate(name: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Gọi trước khi tạo mới, để FE cảnh báo nếu có người bán tên gần giống."""
    candidates = find_possible_duplicates(db, name)
    return [SellerDuplicateCandidate(seller=SellerOut.model_validate(s), similarity_score=score) for s, score in candidates]


@router.post("/", response_model=SellerOut, status_code=status.HTTP_201_CREATED)
def create_seller(payload: SellerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = Seller(
        name=payload.name,
        name_normalized=normalize_name(payload.name),
        address=payload.address,
        id_card_number=payload.id_card_number,
        phone=payload.phone,
    )
    db.add(seller)
    db.flush()
    write_audit_log(
        db,
        entity_type="seller",
        entity_id=seller.id,
        action="create",
        actor_id=current_user.id,
        after_data=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(seller)
    return seller


@router.patch("/{seller_id}", response_model=SellerOut)
def update_seller(seller_id: uuid.UUID, payload: SellerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người bán")

    before = {"name": seller.name, "address": seller.address, "id_card_number": seller.id_card_number, "phone": seller.phone}
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(seller, field, value)
    if "name" in update_data:
        seller.name_normalized = normalize_name(seller.name)

    write_audit_log(
        db,
        entity_type="seller",
        entity_id=seller.id,
        action="update",
        actor_id=current_user.id,
        before_data=before,
        after_data=update_data,
    )
    db.commit()
    db.refresh(seller)
    return seller


@router.post("/{seller_id}/merge-into/{target_seller_id}", response_model=SellerOut)
def merge_seller(seller_id: uuid.UUID, target_seller_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Gộp seller_id vào target_seller_id (VD 2 bản ghi hoá ra là cùng 1 người,
    viết tên khác nhau). KHÔNG xoá bản ghi cũ — chỉ đánh dấu alias, các
    phiếu chi cũ vẫn giữ nguyên liên kết lịch sử.
    """
    seller = db.get(Seller, seller_id)
    target = db.get(Seller, target_seller_id)
    if seller is None or target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người bán")
    if seller.id == target.id:
        raise HTTPException(status_code=400, detail="Không thể gộp 1 người bán vào chính nó")

    seller.alias_of_seller_id = target.id
    write_audit_log(
        db,
        entity_type="seller",
        entity_id=seller.id,
        action="merge",
        actor_id=current_user.id,
        after_data={"alias_of_seller_id": str(target.id)},
    )
    db.commit()
    db.refresh(seller)
    return seller
