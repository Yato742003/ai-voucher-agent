"""
Module xuất file in hàng loạt cuối tháng — kế thừa ĐÚNG logic gom nhóm đã
validate ở giai đoạn xử lý Excel (sắp xếp nhóm theo alphabet tiếng Việt,
giữ thứ tự gốc trong từng nhóm, chèn tiêu đề + ngắt trang mỗi nhóm/phiếu).

Khác biệt so với bản gốc: bản gốc COPY nguyên các block Excel có sẵn;
bản này DỰNG MỚI từng phiếu từ dữ liệu trong DB bằng openpyxl, vì dữ liệu
giờ không còn nằm sẵn trong 1 file Excel định dạng cố định nữa.

Nếu cần khớp tuyệt đối với mẫu Excel gốc của công ty (từng ô, từng merge),
nên cung cấp lại file mẫu trắng để service này "rót" giá trị vào đúng vị
trí, thay vì dựng layout mới như hiện tại — đây là việc tinh chỉnh có thể
làm sau, không chặn việc dùng thử.
"""
import collections
import unicodedata
from datetime import date

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.worksheet.pagebreak import Break
from sqlalchemy import select, extract
from sqlalchemy.orm import Session

from app.models.voucher import Voucher, VoucherStatus
from app.models.seller import Seller
from app.services.number_to_words import number_to_vietnamese_words
from app.services.settings_service import get_setting

BLOCK_HEIGHT = 19
MAXCOL = 10  # cột A..J

_THIN = Side(style="thin")
_BOX = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

HEADER_FONT = Font(name="Times New Roman", size=14, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(fill_type="solid", fgColor="4472C4")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center")

TITLE_FONT = Font(name="Times New Roman", size=16, bold=True)
LABEL_FONT = Font(name="Times New Roman", size=11)
VALUE_FONT = Font(name="Times New Roman", size=11, bold=True)
SMALL_FONT = Font(name="Times New Roman", size=10, italic=True)


def _normalize_for_sort(s: str) -> str:
    s2 = " ".join(s.split())
    s2 = s2.replace("đ", "d").replace("Đ", "D")
    s2 = "".join(c for c in unicodedata.normalize("NFKD", s2) if not unicodedata.combining(c))
    return s2.casefold()


def _fmt_money(amount) -> str:
    return f"{int(amount):,}".replace(",", ".")


def _write_voucher_block(ws: Worksheet, start_row: int, voucher: Voucher, seller: Seller, company_name: str, company_address: str) -> None:
    r = start_row

    ws.cell(row=r, column=1, value=company_name or "CÔNG TY: . . .").font = Font(name="Times New Roman", size=11, bold=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=MAXCOL)

    ws.cell(row=r + 1, column=1, value=f"Địa chỉ: {company_address or '. . .'}").font = SMALL_FONT
    ws.merge_cells(start_row=r + 1, start_column=1, end_row=r + 1, end_column=MAXCOL)

    title_cell = ws.cell(row=r + 3, column=1, value="PHIẾU CHI")
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=r + 3, start_column=1, end_row=r + 3, end_column=MAXCOL)

    ngay_cell = ws.cell(row=r + 4, column=1, value=f"Ngày {voucher.ngay.day:02d} tháng {voucher.ngay.month:02d} năm {voucher.ngay.year}")
    ngay_cell.font = LABEL_FONT
    ws.merge_cells(start_row=r + 4, start_column=1, end_row=r + 4, end_column=5)
    so_cell = ws.cell(row=r + 4, column=7, value=f"Số: {voucher.so_phieu}")
    so_cell.font = VALUE_FONT
    ws.merge_cells(start_row=r + 4, start_column=7, end_row=r + 4, end_column=MAXCOL)

    fields = [
        ("Họ và tên người nhận tiền:", seller.name),
        ("Địa chỉ:", seller.address or ""),
        ("Lý do chi:", voucher.ly_do_chi),
    ]
    for i, (label, value) in enumerate(fields):
        row_idx = r + 5 + i
        lbl = ws.cell(row=row_idx, column=1, value=label)
        lbl.font = LABEL_FONT
        val = ws.cell(row=row_idx, column=3, value=value)
        val.font = VALUE_FONT
        ws.merge_cells(start_row=row_idx, start_column=3, end_row=row_idx, end_column=MAXCOL)

    money_row = r + 8
    lbl = ws.cell(row=money_row, column=1, value="Số tiền:")
    lbl.font = LABEL_FONT
    money_cell = ws.cell(row=money_row, column=3, value=f"{_fmt_money(voucher.so_tien)} đồng")
    money_cell.font = Font(name="Times New Roman", size=12, bold=True)
    money_cell.border = _BOX
    money_cell.alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=money_row, start_column=3, end_row=money_row, end_column=5)

    words_row = r + 9
    lbl2 = ws.cell(row=words_row, column=1, value="Viết bằng chữ:")
    lbl2.font = LABEL_FONT
    words_cell = ws.cell(row=words_row, column=3, value=number_to_vietnamese_words(int(voucher.so_tien)))
    words_cell.font = Font(name="Times New Roman", size=11, italic=True)
    ws.merge_cells(start_row=words_row, start_column=3, end_row=words_row, end_column=MAXCOL)

    sign_header_row = r + 11
    sign_sub_row = r + 12
    roles = ["Giám đốc", "Kế toán trưởng", "Thủ quỹ", "Người lập phiếu", "Người nhận tiền"]
    col = 1
    for role in roles:
        ws.cell(row=sign_header_row, column=col, value=role).font = Font(name="Times New Roman", size=10, bold=True)
        ws.cell(row=sign_header_row, column=col).alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sign_header_row, start_column=col, end_row=sign_header_row, end_column=col + 1)

        sub = ws.cell(row=sign_sub_row, column=col, value="(Ký, họ tên)")
        sub.font = SMALL_FONT
        sub.alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=sign_sub_row, start_column=col, end_row=sign_sub_row, end_column=col + 1)
        col += 2

    for row_idx in range(start_row, start_row + BLOCK_HEIGHT):
        ws.row_dimensions[row_idx].height = 16
    ws.row_dimensions[start_row + 3].height = 24


def export_bang_ke_02_tndn(db: Session, month: int, year: int) -> bytes:
    """
    Xuất "Bảng kê thu mua hàng hóa, dịch vụ mua vào không có hóa đơn"
    (Mẫu 02/TNDN, Thông tư 20/2026/TT-BTC) — đúng 10 cột như mẫu thật của
    công ty: ngày mua, tên người bán, địa chỉ, số căn cước, số điện thoại,
    tên hàng hoá, số lượng, đơn giá, tổng giá thanh toán, ghi chú.

    Đây là bảng liệt kê PHẲNG (không gom nhóm/ngắt trang theo người bán
    như phiếu chi) — đúng cấu trúc mẫu thật: mỗi phiếu chi trong kỳ là
    1 dòng, xếp theo ngày mua tăng dần.
    """
    stmt = (
        select(Voucher)
        .where(
            extract("month", Voucher.ngay) == month,
            extract("year", Voucher.ngay) == year,
            Voucher.trang_thai != VoucherStatus.VOID,
        )
        .order_by(Voucher.ngay, Voucher.so_phieu)
    )
    vouchers = db.execute(stmt).scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = f"BangKe02TNDN_{month:02d}_{year}"

    company_name = get_setting(db, "company_name", "")
    company_address = get_setting(db, "company_address", "")
    company_tax_code = get_setting(db, "company_tax_code", "")

    header_lines = [
        ("TÊN DOANH NGHIỆP:", company_name),
        ("Địa chỉ:", company_address),
        ("Mã số thuế:", company_tax_code),
    ]
    for i, (label, value) in enumerate(header_lines, start=1):
        ws.cell(row=i, column=1, value=f"{label} {value}").font = Font(name="Times New Roman", size=11, bold=(i == 1))

    title_cell = ws.cell(row=5, column=1, value="BẢNG KÊ THU MUA HÀNG HÓA, DỊCH VỤ MUA VÀO KHÔNG CÓ HÓA ĐƠN")
    title_cell.font = Font(name="Times New Roman", size=13, bold=True)
    ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=10)
    title_cell.alignment = Alignment(horizontal="center")

    subtitle = ws.cell(row=6, column=1, value="(Mẫu số 02/TNDN — ban hành kèm theo Thông tư số 20/2026/TT-BTC của Bộ trưởng Bộ Tài chính)")
    subtitle.font = Font(name="Times New Roman", size=10, italic=True)
    ws.merge_cells(start_row=6, start_column=1, end_row=6, end_column=10)
    subtitle.alignment = Alignment(horizontal="center")

    headers = [
        "Ngày tháng năm\nmua hàng", "Tên người bán", "Địa chỉ", "Số căn cước",
        "Số điện thoại\n(nếu có)", "Tên hàng hóa,\ndịch vụ", "Số lượng/\nTrọng lượng",
        "Đơn giá", "Tổng giá\nthanh toán", "Ghi chú",
    ]
    header_row = 8
    for col, text in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=col, value=text)
        c.font = Font(name="Times New Roman", size=10, bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = _BOX
    ws.row_dimensions[header_row].height = 36

    seller_cache: dict = {}
    total_amount = 0
    row = header_row + 1
    for v in vouchers:
        if v.seller_id not in seller_cache:
            seller_cache[v.seller_id] = db.get(Seller, v.seller_id)
        seller = seller_cache[v.seller_id]

        values = [
            f"{v.ngay.day:02d}/{v.ngay.month:02d}/{v.ngay.year}",
            seller.name,
            seller.address or "",
            seller.id_card_number or "",
            seller.phone or "",
            v.ly_do_chi,
            float(v.so_luong) if v.so_luong is not None else "",
            float(v.don_gia) if v.don_gia is not None else "",
            float(v.so_tien),
            "",
        ]
        for col, val in enumerate(values, start=1):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(name="Times New Roman", size=10)
            c.border = _BOX
            if col == 9:
                c.number_format = "#,##0"
        total_amount += float(v.so_tien)
        row += 1

    total_row = row + 1
    ws.cell(row=total_row, column=1, value="Tổng giá trị hàng hóa, dịch vụ mua vào:").font = Font(name="Times New Roman", size=11, bold=True)
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=8)
    total_cell = ws.cell(row=total_row, column=9, value=total_amount)
    total_cell.font = Font(name="Times New Roman", size=11, bold=True)
    total_cell.number_format = "#,##0"

    words_row = total_row + 1
    ws.cell(row=words_row, column=1, value=f"Tiền bằng chữ: {number_to_vietnamese_words(int(total_amount))}").font = Font(
        name="Times New Roman", size=11, italic=True
    )
    ws.merge_cells(start_row=words_row, start_column=1, end_row=words_row, end_column=10)

    sign_row = words_row + 3
    ws.cell(row=sign_row, column=2, value="NGƯỜI LẬP BẢNG KÊ").font = Font(name="Times New Roman", size=10, bold=True)
    ws.cell(row=sign_row, column=2).alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=sign_row, start_column=2, end_row=sign_row, end_column=4)
    ws.cell(row=sign_row, column=7, value="NGƯỜI ĐẠI DIỆN HOẶC\nNGƯỜI ĐƯỢC ỦY QUYỀN").font = Font(name="Times New Roman", size=10, bold=True)
    ws.cell(row=sign_row, column=7).alignment = Alignment(horizontal="center", wrap_text=True)
    ws.merge_cells(start_row=sign_row, start_column=7, end_row=sign_row, end_column=9)

    col_widths = [12, 22, 22, 14, 13, 20, 12, 11, 14, 12]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w

    ws.print_area = f"A1:J{sign_row + 4}"

    from io import BytesIO

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def validate_grouped_by_seller_excel(excel_bytes: bytes, vouchers: list[Voucher], seller_cache: dict) -> dict:
    """
    So sánh đối chiếu output file Excel với nguyên tắc gom nhóm trong gom_nhom_phieu_chi.py.
    Nếu phát hiện dữ liệu không khớp (số phiếu, tổng tiền, tiêu đề nhóm, tên người bán...),
    sẽ ném lỗi ValueError để ngăn không cho tải file.
    """
    import openpyxl
    from io import BytesIO

    wb = openpyxl.load_workbook(BytesIO(excel_bytes), data_only=False)
    ws = wb.active
    if not ws:
        raise ValueError("File Excel xuất ra không chứa bất kỳ sheet nào.")

    # 1. Tìm các block PHIẾU CHI (cột T - col 20)
    title_rows = []
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=20).value
        if v and "PHIẾU CHI" in str(v):
            title_rows.append(r)

    if len(vouchers) == 0:
        if len(title_rows) > 0:
            raise ValueError(f"Không có phiếu chi nào trong CSDL nhưng file Excel lại chứa {len(title_rows)} phiếu.")
        return {"total_vouchers": 0, "num_groups": 0, "total_amount": 0}

    if len(title_rows) == 0:
        raise ValueError(f"Có {len(vouchers)} phiếu chi trong CSDL nhưng file Excel xuất ra không chứa block 'PHIẾU CHI' nào.")

    if len(title_rows) != len(vouchers):
        raise ValueError(
            f"Số lượng phiếu chi trong file Excel ({len(title_rows)}) "
            f"không khớp với số phiếu trong CSDL ({len(vouchers)})."
        )

    # 2. Đọc thông tin từng block trong file Excel
    starts = [r - 3 for r in title_rows]
    parsed_blocks = []
    missing_names = []
    total_excel_amount = 0

    for s in starts:
        name_raw = str(ws.cell(row=s + 7, column=1).value or "").strip()
        so_phieu = str(ws.cell(row=s + 4, column=54).value or "").strip()
        so_tien_val = ws.cell(row=s + 10, column=6).value

        if ":" in name_raw:
            name = name_raw.split(":", 1)[1].strip()
        else:
            name = name_raw.strip()

        if not name:
            missing_names.append(so_phieu or f"Dòng {s}")

        try:
            amt = int(so_tien_val) if so_tien_val is not None else 0
        except (ValueError, TypeError):
            amt = 0
        total_excel_amount += amt
        parsed_blocks.append({"start_row": s, "name": name, "so_phieu": so_phieu, "so_tien": amt})

    if missing_names:
        raise ValueError(f"Phát hiện {len(missing_names)} phiếu trong file Excel chưa có tên người nhận tiền (Số phiếu: {', '.join(missing_names[:5])}).")

    # 3. Kiểm tra danh sách nhóm người bán và thứ tự sắp xếp alphabet
    groups = collections.defaultdict(list)
    for block in parsed_blocks:
        groups[block["name"]].append(block)

    sorted_names = sorted(groups.keys(), key=_normalize_for_sort)

    excel_headers = []
    for r in range(1, ws.max_row + 1):
        val = str(ws.cell(row=r, column=1).value or "")
        if val.startswith("NGƯỜI BÁN:"):
            excel_headers.append((r, val))

    if len(excel_headers) != len(sorted_names):
        raise ValueError(f"Số lượng tiêu đề nhóm người bán trong file Excel ({len(excel_headers)}) không khớp với số người bán thực tế ({len(sorted_names)}).")

    for idx, (hdr_row, hdr_text) in enumerate(excel_headers):
        expected_seller = sorted_names[idx]
        expected_count = len(groups[expected_seller])
        if _normalize_for_sort(expected_seller) not in _normalize_for_sort(hdr_text):
            raise ValueError(f"Dòng tiêu đề thứ {idx + 1} ({hdr_text}) không đúng thứ tự sắp xếp alphabet tiếng Việt. Dự kiến là: {expected_seller}.")
        if f"(Số phiếu: {expected_count})" not in hdr_text:
            raise ValueError(f"Tiêu đề nhóm '{expected_seller}' ghi sai số lượng phiếu. Kỳ vọng (Số phiếu: {expected_count}) nhưng trong file là '{hdr_text}'.")

    # 4. Đối chiếu tổng tiền giữa CSDL và Excel
    db_total_amount = sum(int(v.so_tien) for v in vouchers)
    if total_excel_amount != db_total_amount:
        raise ValueError(f"Lệch tổng tiền: File Excel có tổng tiền {total_excel_amount:,.0f} đ, khác với tổng CSDL {db_total_amount:,.0f} đ.")

    return {
        "total_vouchers": len(parsed_blocks),
        "num_groups": len(sorted_names),
        "total_amount": total_excel_amount,
        "status": "VALIDATED_OK"
    }


def export_grouped_by_seller(db: Session, month: int, year: int) -> bytes:
    """
    Trả về nội dung file .xlsx (bytes) — toàn bộ phiếu chi hợp lệ (không phải
    VOID) trong kỳ, gom nhóm theo người bán, sắp alphabet, có tiêu đề +
    ngắt trang mỗi nhóm/phiếu — y hệt nguyên tắc trong gom_nhom_phieu_chi.py.
    """
    import os
    import copy
    from pathlib import Path
    import openpyxl
    from openpyxl.worksheet.pagebreak import Break
    from io import BytesIO

    CURRENT_DIR = Path(__file__).resolve().parent
    TEMPLATE_PATH = CURRENT_DIR.parent / "resources" / "template_voucher.xlsx"

    stmt = (
        select(Voucher)
        .where(
            extract("month", Voucher.ngay) == month,
            extract("year", Voucher.ngay) == year,
            Voucher.trang_thai != VoucherStatus.VOID,
        )
        .order_by(Voucher.so_phieu)
    )
    vouchers = db.execute(stmt).scalars().all()

    groups: dict[str, list[Voucher]] = collections.defaultdict(list)
    seller_cache: dict = {}

    def clean_prefix(val, prefix: str) -> str:
        if not val:
            return ""
        val_str = str(val).strip()
        prefix_lower = prefix.strip().lower()
        val_lower = val_str.lower()
        if val_lower.startswith(prefix_lower):
            remainder = val_str[len(prefix):].strip()
            if remainder.startswith(":"):
                remainder = remainder[1:].strip()
            return remainder
        return val_str

    for v in vouchers:
        if v.seller_id not in seller_cache:
            seller_cache[v.seller_id] = db.get(Seller, v.seller_id)
        seller = seller_cache[v.seller_id]
        groups[seller.name].append(v)

    sorted_names = sorted(groups.keys(), key=_normalize_for_sort)

    company_name = get_setting(db, "company_name", "")
    company_address = get_setting(db, "company_address", "")
    company_tax_code = get_setting(db, "company_tax_code", "")

    # Load template sheet
    wb_template = openpyxl.load_workbook(str(TEMPLATE_PATH), data_only=False)
    ws_template = wb_template["LUU"]

    # Cache merges of the template block (row 1 to 21)
    template_merges = []
    for mc in list(ws_template.merged_cells.ranges):
        min_col, min_row, max_col, max_row = mc.bounds
        if min_row <= 21 and max_row <= 21:
            template_merges.append((min_row - 1, min_col, max_row - 1, max_col))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"PhieuChi_{month:02d}_{year}"

    # Copy column dimensions from template
    for col_letter, dim in ws_template.column_dimensions.items():
        nd = ws.column_dimensions[col_letter]
        nd.width = dim.width
        nd.hidden = dim.hidden

    ws.sheet_format.defaultRowHeight = ws_template.sheet_format.defaultRowHeight
    ws.sheet_format.defaultColWidth = ws_template.sheet_format.defaultColWidth
    ws.page_setup.orientation = ws_template.page_setup.orientation
    ws.page_setup.paperSize = ws_template.page_setup.paperSize
    ws.page_setup.fitToHeight = ws_template.page_setup.fitToHeight
    ws.page_setup.fitToWidth = ws_template.page_setup.fitToWidth
    ws.page_margins.left = ws_template.page_margins.left
    ws.page_margins.right = ws_template.page_margins.right
    ws.page_margins.top = ws_template.page_margins.top
    ws.page_margins.bottom = ws_template.page_margins.bottom
    ws.page_margins.header = ws_template.page_margins.header
    ws.page_margins.footer = ws_template.page_margins.footer
    ws.sheet_view.showGridLines = ws_template.sheet_view.showGridLines

    block_height = 21
    max_col = 62

    def copy_block(row_dest, voucher: Voucher, seller: Seller):
        delta = row_dest - 1
        for r in range(1, 22):
            src_rd = ws_template.row_dimensions.get(r)
            if src_rd is not None and src_rd.height is not None:
                ws.row_dimensions[row_dest + r - 1].height = src_rd.height
            for c in range(1, max_col + 1):
                src_cell = ws_template.cell(row=r, column=c)
                if src_cell.value is None and not src_cell.has_style:
                    continue
                dst_cell = ws.cell(row=row_dest + r - 1, column=c)
                dst_cell.value = src_cell.value
                if src_cell.has_style:
                    dst_cell.font = copy.copy(src_cell.font)
                    dst_cell.border = copy.copy(src_cell.border)
                    dst_cell.fill = copy.copy(src_cell.fill)
                    dst_cell.number_format = src_cell.number_format
                    dst_cell.protection = copy.copy(src_cell.protection)
                    dst_cell.alignment = copy.copy(src_cell.alignment)

        for rel_min_row, min_col, rel_max_row, max_c in template_merges:
            ws.merge_cells(
                start_row=row_dest + rel_min_row, start_column=min_col,
                end_row=row_dest + rel_max_row, end_column=max_c,
            )

        # Overwrite values with actual data
        ws.cell(row=row_dest, column=1, value=company_name or "CÔNG TY: . . .")
        
        clean_company_address = clean_prefix(company_address, "Địa chỉ")
        ws.cell(row=row_dest + 1, column=1, value=f"Địa chỉ : {clean_company_address or '. . .'}")
        
        clean_tax_code = clean_prefix(company_tax_code, "Mã số thuế")
        ws.cell(row=row_dest + 2, column=1, value=f"Mã số thuế :  {clean_tax_code or '. . .'}")
        
        ws.cell(row=row_dest + 4, column=20, value=f"Ngày {voucher.ngay.day:02d} tháng {voucher.ngay.month:02d} năm {voucher.ngay.year}")
        ws.cell(row=row_dest + 5, column=54, value=str(voucher.so_phieu))
        ws.cell(row=row_dest + 6, column=54, value="1561") # Nợ
        ws.cell(row=row_dest + 7, column=54, value="1111") # Có
        
        clean_seller_name = clean_prefix(seller.name, "Họ và tên người nhận tiền")
        ws.cell(row=row_dest + 7, column=1, value=f"Họ và tên người nhận tiền :  {clean_seller_name.upper()}")
        
        clean_seller_address = clean_prefix(seller.address, "Địa chỉ")
        ws.cell(row=row_dest + 8, column=1, value=f"Địa chỉ :  {clean_seller_address}")
        
        clean_reason = clean_prefix(voucher.ly_do_chi, "Lý do chi")
        ws.cell(row=row_dest + 9, column=1, value=f"Lý do chi :  {clean_reason}")
        ws.cell(row=row_dest + 10, column=6, value=int(voucher.so_tien))
        ws.cell(row=row_dest + 10, column=18, value=f"(Viết bằng chữ) : {number_to_vietnamese_words(int(voucher.so_tien))}")
        ws.cell(row=row_dest + 12, column=55, value=f"Ngày {voucher.ngay.day:02d} tháng {voucher.ngay.month:02d} năm {voucher.ngay.year}")
        # Clear signer names in row 20
        ws.cell(row=row_dest + 19, column=8, value="")
        ws.cell(row=row_dest + 19, column=21, value="")
        ws.cell(row=row_dest + 19, column=32, value="")
        ws.cell(row=row_dest + 19, column=43, value="")
        ws.cell(row=row_dest + 20, column=1, value=f"Đã nhận đủ số tiền viết bằng chữ : {number_to_vietnamese_words(int(voucher.so_tien))}")

    row_breaks = []
    cur = 1
    for name in sorted_names:
        group_vouchers = groups[name]
        sep_row = cur
        ws.row_dimensions[sep_row].height = 30
        cell = ws.cell(row=sep_row, column=1, value=f"NGƯỜI BÁN: {name}    (Số phiếu: {len(group_vouchers)})")
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        for c in range(2, max_col + 1):
            ws.cell(row=sep_row, column=c).fill = HEADER_FILL
        ws.merge_cells(start_row=sep_row, start_column=1, end_row=sep_row, end_column=max_col)
        row_breaks.append(sep_row)
        cur += 1

        for v in group_vouchers:
            seller = seller_cache[v.seller_id]
            copy_block(cur, v, seller)
            cur += block_height
            row_breaks.append(cur - 1)

    for r in row_breaks[:-1]:
        ws.row_breaks.append(Break(id=r))

    if cur > 1:
        ws.print_area = f"A1:BJ{cur - 1}"

    buf = BytesIO()
    wb.save(buf)
    excel_bytes = buf.getvalue()

    # Bước Validate: So sánh đối chiếu output file Excel với nguyên tắc gom nhóm gom_nhom_phieu_chi.py
    validate_grouped_by_seller_excel(excel_bytes, vouchers, seller_cache)

    return excel_bytes
