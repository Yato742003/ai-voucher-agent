"""Đổi số tiền (VND) sang chữ tiếng Việt — dùng cho trường "Tiền bằng chữ" trên phiếu chi/hoá đơn."""

_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_UNITS = ["", "nghìn", "triệu", "tỷ"]


def _three_digits_to_words(n: int, full: bool) -> str:
    """n trong khoảng 0-999. `full`=True nghĩa là nhóm này không phải nhóm đầu tiên
    (VD "1 triệu 005 nghìn" cần đọc là "một triệu không trăm lẻ năm nghìn")."""
    hundreds, rest = divmod(n, 100)
    tens, units = divmod(rest, 10)

    words = []
    if hundreds > 0 or full:
        words.append(_DIGITS[hundreds] + " trăm")
    if tens == 0:
        if units > 0:
            words.append("lẻ" if (hundreds > 0 or full) else "")
            words.append(_DIGITS[units])
    elif tens == 1:
        words.append("mười")
        if units > 0:
            words.append("một" if units == 1 else ("lăm" if units == 5 else _DIGITS[units]))
    else:
        words.append(_DIGITS[tens] + " mươi")
        if units == 1:
            words.append("mốt")
        elif units == 5:
            words.append("lăm")
        elif units > 0:
            words.append(_DIGITS[units])

    return " ".join(w for w in words if w)


def number_to_vietnamese_words(amount: int) -> str:
    """
    VD: 66144000 -> "sáu mươi sáu triệu một trăm bốn mươi bốn nghìn đồng"
    Chỉ nhận số nguyên (VND không có phần thập phân trong nghiệp vụ này).
    """
    if amount == 0:
        return "không đồng"
    if amount < 0:
        return "âm " + number_to_vietnamese_words(-amount)

    groups = []
    n = amount
    while n > 0:
        groups.append(n % 1000)
        n //= 1000

    parts = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        is_not_first_written_group = len(parts) > 0
        words = _three_digits_to_words(g, full=is_not_first_written_group)
        parts.append(f"{words} {_UNITS[i]}".strip())

    result = " ".join(parts) + " đồng"
    # viết hoa chữ cái đầu cho đúng văn phong chứng từ
    return result[0].upper() + result[1:]
