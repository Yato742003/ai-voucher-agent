import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerUpdate, CustomerOut
from app.api.deps import get_current_user
from app.core.audit import write_audit_log

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.execute(select(Customer).order_by(Customer.company_name)).scalars().all()


@router.post("/", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.flush()
    write_audit_log(
        db, entity_type="customer", entity_id=customer.id, action="create",
        actor_id=current_user.id, after_data=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: uuid.UUID, payload: CustomerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách hàng")

    update_data = payload.model_dump(exclude_unset=True)
    before = {k: getattr(customer, k) for k in update_data}
    for field, value in update_data.items():
        setattr(customer, field, value)

    write_audit_log(
        db, entity_type="customer", entity_id=customer.id, action="update",
        actor_id=current_user.id, before_data=before, after_data=update_data,
    )
    db.commit()
    db.refresh(customer)
    return customer
