"""
Cấp số phiếu tự động — không cho nhập tay để tránh trùng/nhảy số
(rủi ro đã nêu trong kế hoạch, mục 3.1).

Định dạng theo đúng cách công ty đang dùng: "001/06" (số thứ tự / tháng),
đếm lại từ 001 mỗi tháng mới.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import SequenceCounter


def get_next_voucher_number(db: Session, ngay: date, prefix: str = "PC") -> str:
    """
    Lấy số phiếu tiếp theo cho tháng của `ngay`. Dùng SELECT ... FOR UPDATE
    để khoá đúng 1 dòng counter — nếu 2 request tạo phiếu cùng lúc, request
    thứ 2 phải đợi request thứ 1 commit/rollback xong mới đọc được số mới
    nhất, tránh 2 phiếu bị cấp trùng số.

    Lưu ý: hàm này KHÔNG tự commit — caller (API endpoint) phải commit
    cùng transaction với việc tạo Voucher, để nếu tạo phiếu lỗi thì số
    cũng không bị "mất" (rollback cả hai).
    """
    stmt = (
        select(SequenceCounter)
        .where(
            SequenceCounter.prefix == prefix,
            SequenceCounter.year == ngay.year,
            SequenceCounter.month == ngay.month,
        )
        .with_for_update()
    )
    counter = db.execute(stmt).scalar_one_or_none()

    if counter is None:
        counter = SequenceCounter(prefix=prefix, year=ngay.year, month=ngay.month, last_number=0)
        db.add(counter)
        db.flush()

    counter.last_number += 1
    db.flush()

    return f"{counter.last_number:03d}/{ngay.month:02d}"
