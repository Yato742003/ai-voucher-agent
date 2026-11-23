"""
Phát hiện người bán có khả năng trùng khi tạo mới — vì trong dữ liệu Excel
cũ đã từng gặp tình trạng cùng 1 người bị ghi tên khác nhau (khác hoa/thường,
khoảng trắng...), dẫn đến khó tổng hợp đúng.
"""
from rapidfuzz import fuzz

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.seller import Seller, normalize_name

SIMILARITY_WARNING_THRESHOLD = 85.0  # 0-100, ngưỡng để cảnh báo trùng


def find_possible_duplicates(db: Session, candidate_name: str, limit: int = 5) -> list[tuple[Seller, float]]:
    """
    Trả về danh sách (Seller, điểm giống nhau) cho các người bán hiện có
    có tên tương tự `candidate_name`, sắp giảm dần theo độ giống, chỉ lấy
    những người có điểm >= SIMILARITY_WARNING_THRESHOLD.

    Đây là gợi ý cảnh báo cho người dùng xác nhận — KHÔNG tự động chặn
    hay tự gộp record, vì có thể có 2 người bán trùng tên thật (khác người).
    """
    normalized_candidate = normalize_name(candidate_name)

    all_sellers = db.execute(select(Seller).where(Seller.alias_of_seller_id.is_(None))).scalars().all()

    scored = []
    for seller in all_sellers:
        score = fuzz.ratio(normalized_candidate, seller.name_normalized)
        if score >= SIMILARITY_WARNING_THRESHOLD:
            scored.append((seller, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]
