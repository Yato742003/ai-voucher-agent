"""
gom_nhom_phieu_chi.py
=======================================================================
Công cụ gom nhóm "Phiếu chi" (payment voucher) theo NGƯỜI BÁN
(người nhận tiền), để in/photocopy dễ dàng hơn.

BỐI CẢNH / GIẢ ĐỊNH VỀ CẤU TRÚC FILE ĐẦU VÀO
-----------------------------------------------------------------------
File Excel đầu vào có 2 sheet:
  - "CHI" : mẫu phiếu đang hiển thị để in (1 phiếu).
  - "LUU" : kho lưu toàn bộ các phiếu đã lập. Mỗi phiếu chiếm một số
            dòng cố định (thường là 21 dòng/phiếu), xếp liên tiếp từ
            trên xuống dưới. Dòng đầu tiên (block đầu tiên) là MẪU
            TRỐNG (template), không phải phiếu thật, và luôn bị loại
            khỏi vùng in (print_area) của sheet gốc -> script cũng bỏ
            qua block này khi gom nhóm.

Trong mỗi block-phiếu:
  - Ô tại cột T (cột 20), dòng thứ 4 của block chứa chữ "PHIẾU CHI"
    -> dùng để dò vị trí bắt đầu của từng phiếu.
  - Ô tại cột A (cột 1), dòng thứ 8 của block chứa:
        "Họ và tên người nhận tiền :  <TÊN NGƯỜI BÁN>"
    -> đây là trường dùng để GOM NHÓM.
  - Ô tại cột BB (cột 54), dòng thứ 5 của block chứa số phiếu (VD: 001/06).
  - Ô tại cột F (cột 6), dòng thứ 11 của block chứa số tiền.

Nếu cấu trúc file thực tế của bạn khác (số cột/dòng lệch), chỉnh lại
các hằng số OFFSET_* bên dưới cho đúng.

QUY TRÌNH SCRIPT THỰC HIỆN
-----------------------------------------------------------------------
1. Dò tất cả các block-phiếu thật trong sheet "LUU" (bỏ qua block mẫu
   đầu tiên) bằng cách tìm các dòng chứa chữ "PHIẾU CHI".
2. Đọc tên người nhận tiền của từng phiếu. Nếu có phiếu nào CHƯA CÓ TÊN
   -> DỪNG LẠI và báo cho người dùng biết chính xác những phiếu nào
   (theo "Số phiếu") đang thiếu tên, để bổ sung trước khi chạy lại.
   (Script sẽ không tự chế/đoán tên.)
3. Gom các phiếu theo tên người bán; trong cùng 1 người bán, GIỮ NGUYÊN
   thứ tự gốc (thường là theo thời gian).
4. Sắp xếp các NHÓM theo thứ tự alphabet tiếng Việt (bỏ dấu để so sánh,
   "Đ" xếp sau "D") để dễ tra cứu khi in.
5. Tạo 1 FILE MỚI, HOÀN TOÀN ĐỘC LẬP (không đụng gì đến file gốc),
   chỉ có một sheet duy nhất chứa các phiếu đã gom nhóm, với:
     - 1 dòng tiêu đề màu xanh trước mỗi nhóm: "NGƯỜI BÁN: ... (Số phiếu: N)"
     - Ngắt trang (page break) sau mỗi tiêu đề và sau mỗi phiếu, để khi
       in, mỗi phiếu / mỗi tiêu đề nhóm nằm gọn trên 1 trang.
     - Giữ nguyên toàn bộ định dạng gốc của từng phiếu: font, merge ô,
       chiều cao dòng, độ rộng cột, number format, page setup, margins...
     - KHÔNG sửa/xóa/thêm bất kỳ giá trị dữ liệu nào của phiếu gốc -
       chỉ copy nguyên văn sang vị trí mới.
6. Không format cell/formula động nào được tạo ra (toàn bộ là giá trị
   copy nguyên bản) -> file mở lên là dùng in được ngay, không cần
   "Enable Editing" hay tính lại công thức.

CÁCH DÙNG
-----------------------------------------------------------------------
Cần cài thư viện openpyxl (chỉ cần cài 1 lần):
    pip install openpyxl

Chạy từ dòng lệnh:
    python gom_nhom_phieu_chi.py "PHIEU_CHI_THANG_X.xlsx" "KET_QUA.xlsx"

Hoặc gọi trực tiếp trong Python:
    from gom_nhom_phieu_chi import process
    info = process("PHIEU_CHI_THANG_X.xlsx", "KET_QUA.xlsx")
    print(info)
=======================================================================
"""

import sys
import collections
import copy
import unicodedata

import openpyxl
from openpyxl.worksheet.pagebreak import Break
from openpyxl.styles import Font, PatternFill, Alignment


# ----------------------------------------------------------------------
# CẤU HÌNH (chỉnh nếu cấu trúc file của bạn khác mẫu chuẩn)
# ----------------------------------------------------------------------
SHEET_NAME = "LUU"          # tên sheet chứa toàn bộ phiếu
TITLE_COL = 20              # cột T - nơi in chữ "PHIẾU CHI"
NAME_COL = 1                # cột A - nơi in "Họ và tên người nhận tiền"
NAME_ROW_OFFSET = 7         # dòng chứa tên, tính từ đầu block (0-indexed)
TITLE_ROW_OFFSET = 3        # dòng chứa chữ "PHIẾU CHI", tính từ đầu block
SO_PHIEU_COL = 54           # cột BB - nơi in "Số phiếu"
SO_PHIEU_ROW_OFFSET = 4     # dòng chứa số phiếu, tính từ đầu block
MAXCOL = 62                 # cột cuối cùng có dữ liệu (BJ)

HEADER_FONT = Font(name="Times New Roman", size=14, bold=True, color="FFFFFF")
HEADER_FILL = PatternFill(fill_type="solid", fgColor="4472C4")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center")


def _normalize_for_sort(s: str) -> str:
    """Chuẩn hoá tên để sắp xếp alphabet tiếng Việt (bỏ dấu, 'đ' -> 'd')."""
    s2 = " ".join(s.split())
    s2 = s2.replace("đ", "d").replace("Đ", "D")
    s2 = "".join(c for c in unicodedata.normalize("NFKD", s2) if not unicodedata.combining(c))
    return s2.casefold()


def _detect_blocks(ws):
    """
    Tìm vị trí bắt đầu (start row) của từng block-phiếu THẬT trong sheet,
    tự động phát hiện chiều cao block (số dòng/phiếu) và bỏ qua block
    mẫu đầu tiên.

    Trả về: (block_height, list_of_start_rows)
    """
    title_rows = []
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=TITLE_COL).value
        if v and "PHIẾU CHI" in str(v):
            title_rows.append(r)

    if len(title_rows) < 2:
        raise ValueError(
            "Không tìm đủ các block 'PHIẾU CHI' trong sheet để xác định "
            "cấu trúc file. Kiểm tra lại TITLE_COL / tên sheet."
        )

    diffs = {title_rows[i + 1] - title_rows[i] for i in range(len(title_rows) - 1)}
    if len(diffs) != 1:
        raise ValueError(
            f"Chiều cao các block-phiếu không đồng nhất ({diffs}). "
            "Cần kiểm tra lại file, có thể có phiếu bị chèn/xoá dòng thủ công."
        )
    block_height = diffs.pop()

    # bỏ block đầu tiên (mẫu/template, không phải phiếu thật)
    starts = [r - TITLE_ROW_OFFSET for r in title_rows[1:]]
    return block_height, starts


def _get_name(ws, start_row):
    raw = ws.cell(row=start_row + NAME_ROW_OFFSET, column=NAME_COL).value or ""
    return raw.split(":", 1)[1].strip() if ":" in raw else raw.strip()


def _get_so_phieu(ws, start_row):
    return ws.cell(row=start_row + SO_PHIEU_ROW_OFFSET, column=SO_PHIEU_COL).value


def process(src_path: str, out_path: str, sheet_title: str = "PHIEU_GOM_NHOM") -> dict:
    """
    Đọc file phiếu chi tại src_path, gom nhóm theo người bán, xuất ra
    file mới tại out_path (chỉ 1 sheet, độc lập với file gốc).

    Trả về dict thông tin tóm tắt: tổng số phiếu, số nhóm, danh sách
    (tên người bán, số lượng phiếu) đã sắp xếp.
    """
    wb_src = openpyxl.load_workbook(src_path, data_only=False)
    if SHEET_NAME not in wb_src.sheetnames:
        raise ValueError(f"Không tìm thấy sheet '{SHEET_NAME}' trong file {src_path}")
    ws_src = wb_src[SHEET_NAME]

    block_height, starts = _detect_blocks(ws_src)

    # --- Bước 1: đọc tên người bán của từng phiếu, kiểm tra thiếu sót ---
    blocks = [(s, _get_name(ws_src, s)) for s in starts]
    missing = [(_get_so_phieu(ws_src, s), s) for s, name in blocks if not name]
    if missing:
        so_list = ", ".join(str(so) for so, _ in missing[:20])
        more = "" if len(missing) <= 20 else f" ... và {len(missing) - 20} phiếu khác"
        raise ValueError(
            f"Còn {len(missing)} phiếu CHƯA CÓ tên người nhận tiền, "
            f"không thể tự gom nhóm. Số phiếu bị thiếu: {so_list}{more}. "
            "Vui lòng bổ sung tên trong file gốc rồi chạy lại."
        )

    # --- Bước 2: gom nhóm theo tên, giữ nguyên thứ tự gốc trong từng nhóm ---
    groups = collections.defaultdict(list)
    for s, name in blocks:
        groups[name].append(s)
    sorted_names = sorted(groups.keys(), key=_normalize_for_sort)

    # --- Bước 3: gom các vùng merge cell theo từng block, để copy lại đúng ---
    merges_by_start = collections.defaultdict(list)
    for mc in list(ws_src.merged_cells.ranges):
        min_col, min_row, max_col, max_row = mc.bounds
        for s in starts:
            if s <= min_row and max_row <= s + block_height - 1:
                merges_by_start[s].append((min_row - s, min_col, max_row - s, max_col))
                break

    # --- Bước 4: tạo workbook mới, độc lập, copy cấu hình trang/cột ---
    wb_new = openpyxl.Workbook()
    ws_new = wb_new.active
    ws_new.title = sheet_title

    for col_letter, dim in ws_src.column_dimensions.items():
        nd = ws_new.column_dimensions[col_letter]
        nd.width = dim.width
        nd.hidden = dim.hidden

    ws_new.sheet_format.defaultRowHeight = ws_src.sheet_format.defaultRowHeight
    ws_new.sheet_format.defaultColWidth = ws_src.sheet_format.defaultColWidth
    ws_new.page_setup.orientation = ws_src.page_setup.orientation
    ws_new.page_setup.paperSize = ws_src.page_setup.paperSize
    ws_new.page_setup.fitToHeight = ws_src.page_setup.fitToHeight
    ws_new.page_setup.fitToWidth = ws_src.page_setup.fitToWidth
    ws_new.page_margins.left = ws_src.page_margins.left
    ws_new.page_margins.right = ws_src.page_margins.right
    ws_new.page_margins.top = ws_src.page_margins.top
    ws_new.page_margins.bottom = ws_src.page_margins.bottom
    ws_new.page_margins.header = ws_src.page_margins.header
    ws_new.page_margins.footer = ws_src.page_margins.footer
    ws_new.sheet_view.showGridLines = ws_src.sheet_view.showGridLines

    def copy_block(start_src, row_dest):
        """Copy nguyên 1 block-phiếu (giá trị + toàn bộ định dạng + merge)."""
        delta = row_dest - start_src
        for r in range(start_src, start_src + block_height):
            src_rd = ws_src.row_dimensions.get(r)
            if src_rd is not None and src_rd.height is not None:
                ws_new.row_dimensions[r + delta].height = src_rd.height
            for c in range(1, MAXCOL + 1):
                src_cell = ws_src.cell(row=r, column=c)
                if src_cell.value is None and not src_cell.has_style:
                    continue
                dst_cell = ws_new.cell(row=r + delta, column=c)
                dst_cell.value = src_cell.value
                if src_cell.has_style:
                    dst_cell.font = copy.copy(src_cell.font)
                    dst_cell.border = copy.copy(src_cell.border)
                    dst_cell.fill = copy.copy(src_cell.fill)
                    dst_cell.number_format = src_cell.number_format
                    dst_cell.protection = copy.copy(src_cell.protection)
                    dst_cell.alignment = copy.copy(src_cell.alignment)
        for rel_min_row, min_col, rel_max_row, max_col in merges_by_start.get(start_src, []):
            ws_new.merge_cells(
                start_row=start_src + rel_min_row + delta, start_column=min_col,
                end_row=start_src + rel_max_row + delta, end_column=max_col,
            )

    # --- Bước 5: ghi từng nhóm: 1 dòng tiêu đề + các phiếu của nhóm đó ---
    row_breaks = []
    cur = 1
    for name in sorted_names:
        block_starts = groups[name]
        n = len(block_starts)

        sep_row = cur
        ws_new.row_dimensions[sep_row].height = 30
        cell = ws_new.cell(row=sep_row, column=1, value=f"NGƯỜI BÁN: {name}    (Số phiếu: {n})")
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        for c in range(2, MAXCOL + 1):
            ws_new.cell(row=sep_row, column=c).fill = HEADER_FILL
        ws_new.merge_cells(start_row=sep_row, start_column=1, end_row=sep_row, end_column=MAXCOL)
        row_breaks.append(sep_row)
        cur += 1

        for s in block_starts:
            copy_block(s, cur)
            cur += block_height
            row_breaks.append(cur - 1)

    # ngắt trang sau mỗi tiêu đề nhóm và sau mỗi phiếu (trừ dòng cuối cùng)
    for r in row_breaks[:-1]:
        ws_new.row_breaks.append(Break(id=r))

    ws_new.print_area = f"A1:BJ{cur - 1}"
    ws_new.sheet_properties.tabColor = "4472C4"

    wb_new.save(out_path)

    return {
        "total_vouchers": len(blocks),
        "num_groups": len(sorted_names),
        "total_rows": cur - 1,
        "groups": [(name, len(groups[name])) for name in sorted_names],
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        print("Cách dùng: python gom_nhom_phieu_chi.py <file_dau_vao.xlsx> <file_ket_qua.xlsx>")
        sys.exit(1)

    src_path, out_path = sys.argv[1], sys.argv[2]
    try:
        info = process(src_path, out_path)
    except ValueError as e:
        print(f"LỖI: {e}")
        sys.exit(1)

    print(f"Đã xử lý xong: {src_path} -> {out_path}")
    print(f"Tổng số phiếu: {info['total_vouchers']}")
    print(f"Số người bán: {info['num_groups']}")
    print("Chi tiết theo từng người bán:")
    for name, count in info["groups"]:
        print(f"  {count:>3}  {name}")
