"""
Import dữ liệu phiếu chi LỊCH SỬ từ các file Excel .xlsx vào Database.
"""
import argparse
import re
import sys
from datetime import datetime, date
from pathlib import Path

import openpyxl
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import SessionLocal  # noqa: E402
from app.models.seller import Seller, normalize_name  # noqa: E402
from app.models.voucher import Voucher, VoucherStatus  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.account import SequenceCounter  # noqa: E402
from app.migration.excel_import_helpers import (  # noqa: E402
    TITLE_COL,
    NAME_COL,
    NAME_ROW_OFFSET,
    ADDRESS_ROW_OFFSET,
    REASON_ROW_OFFSET,
    AMOUNT_ROW_OFFSET,
    AMOUNT_COL,
    TITLE_ROW_OFFSET,
    SO_PHIEU_COL,
    SO_PHIEU_ROW_OFFSET,
    DATE_COL,
    DATE_ROW_OFFSET,
    label_value as _label_value,
    parse_date as _parse_date,
    get_target_sheet as _get_target_sheet,
    detect_blocks as _detect_blocks,
    resolve_excel_files,
    is_file_imported,
    mark_file_imported,
)
from app.core.audit import write_audit_log  # noqa: E402


def import_file(
    xlsx_path: str,
    created_by_username: str = "admin",
    dry_run: bool = False,
    force: bool = False,
    db_session=None,
) -> dict:
    file_path = Path(xlsx_path)
    filename = file_path.name

    should_close_db = False
    if db_session is None:
        db = SessionLocal()
        should_close_db = True
    else:
        db = db_session

    try:
        if not force and is_file_imported(db, filename):
            return {
                "file": filename,
                "status": "skipped",
                "reason": "already_imported",
                "imported": 0,
                "total": 0,
                "skipped_existing": 0,
                "sellers_created": 0,
            }

        wb = openpyxl.load_workbook(str(file_path), data_only=True)
        ws = _get_target_sheet(wb)
        _, starts = _detect_blocks(ws)

        creator = db.execute(select(User).where(User.username == created_by_username)).scalar_one_or_none()
        if creator is None:
            raise ValueError(f"Không tìm thấy user '{created_by_username}' — hãy chạy seed_initial_data.py trước")

        stats = {
            "file": filename,
            "status": "success",
            "total": 0,
            "imported": 0,
            "skipped_existing": 0,
            "skipped_no_name": 0,
            "sellers_created": 0,
        }

        max_number_by_month: dict[tuple[int, int], int] = {}

        for s in starts:
            stats["total"] += 1
            so_phieu = ws.cell(row=s + SO_PHIEU_ROW_OFFSET, column=SO_PHIEU_COL).value
            ngay = _parse_date(ws.cell(row=s + DATE_ROW_OFFSET, column=DATE_COL).value)
            name = _label_value(ws.cell(row=s + NAME_ROW_OFFSET, column=NAME_COL).value)
            address = _label_value(ws.cell(row=s + ADDRESS_ROW_OFFSET, column=NAME_COL).value)
            reason = _label_value(ws.cell(row=s + REASON_ROW_OFFSET, column=NAME_COL).value)
            amount = ws.cell(row=s + AMOUNT_ROW_OFFSET, column=AMOUNT_COL).value

            if not name:
                stats["skipped_no_name"] += 1
                print(f"  [BỎ QUA - thiếu tên] số phiếu {so_phieu}")
                continue
            if not so_phieu or not ngay or not amount:
                stats["skipped_no_name"] += 1
                print(f"  [BỎ QUA - thiếu dữ liệu bắt buộc] số phiếu {so_phieu}")
                continue

            existing = db.execute(select(Voucher).where(Voucher.so_phieu == str(so_phieu))).scalar_one_or_none()
            if existing is not None:
                if existing.trang_thai == VoucherStatus.VOID:
                    norm = normalize_name(name)
                    seller = db.execute(select(Seller).where(Seller.name_normalized == norm)).scalar_one_or_none()
                    if seller is None:
                        seller = Seller(name=name, name_normalized=norm, address=address or None)
                        db.add(seller)
                        db.flush()
                        stats["sellers_created"] += 1
                    
                    existing.ngay = ngay
                    existing.seller_id = seller.id
                    existing.ly_do_chi = reason or "(không rõ — nhập từ dữ liệu lịch sử)"
                    existing.so_tien = amount
                    existing.trang_thai = VoucherStatus.ARCHIVED
                    existing.created_by = creator.id
                    db.flush()
                    
                    write_audit_log(
                        db,
                        entity_type="voucher",
                        entity_id=existing.id,
                        action="import_overwrite_void",
                        actor_id=creator.id,
                        after_data={"source_file": filename, "so_phieu": str(so_phieu)},
                    )
                    stats["imported"] += 1
                    print(f"  [GHI ĐÈ - cập nhật phiếu huỷ {so_phieu}] người bán: {name}")
                    continue
                else:
                    stats["skipped_existing"] += 1
                    print(f"  [BỎ QUA - trùng số phiếu {so_phieu}] người bán: {name}")
                    continue

            norm = normalize_name(name)
            seller = db.execute(select(Seller).where(Seller.name_normalized == norm)).scalar_one_or_none()
            if seller is None:
                seller = Seller(name=name, name_normalized=norm, address=address or None)
                db.add(seller)
                db.flush()
                stats["sellers_created"] += 1

            voucher = Voucher(
                so_phieu=str(so_phieu),
                ngay=ngay,
                seller_id=seller.id,
                ly_do_chi=reason or "(không rõ — nhập từ dữ liệu lịch sử)",
                so_tien=amount,
                trang_thai=VoucherStatus.ARCHIVED,
                created_by=creator.id,
            )
            db.add(voucher)
            db.flush()

            write_audit_log(
                db,
                entity_type="voucher",
                entity_id=voucher.id,
                action="import_from_excel",
                actor_id=creator.id,
                after_data={"source_file": filename, "so_phieu": str(so_phieu)},
            )

            key = (ngay.year, ngay.month)
            m = re.match(r"(\d+)", str(so_phieu))
            if m:
                num = int(m.group(1))
                max_number_by_month[key] = max(max_number_by_month.get(key, 0), num)

            stats["imported"] += 1

        for (year, month), max_num in max_number_by_month.items():
            counter = db.execute(
                select(SequenceCounter).where(
                    SequenceCounter.prefix == "PC", SequenceCounter.year == year, SequenceCounter.month == month
                )
            ).scalar_one_or_none()
            if counter is None:
                counter = SequenceCounter(prefix="PC", year=year, month=month, last_number=max_num)
                db.add(counter)
            elif counter.last_number < max_num:
                counter.last_number = max_num

        if not dry_run:
            mark_file_imported(db, filename)
            db.commit()
        else:
            db.rollback()

        return stats
    except Exception as e:
        if should_close_db:
            db.rollback()
        raise e
    finally:
        if should_close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="Import dữ liệu phiếu chi lịch sử từ file Excel (.xlsx)")
    parser.add_argument("path", help="Đường dẫn tới file .xlsx hoặc thư mục chứa các file .xlsx")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm không lưu vào database")
    parser.add_argument("--force", action="store_true", help="Bắt buộc import lại dù file đã đánh dấu đã import")
    parser.add_argument("--user", default="admin", help="Tên user thực hiện import (mặc định: admin)")

    args = parser.parse_args()

    target_files = resolve_excel_files(args.path)
    if not target_files:
        print(f"[FAIL] Không tìm thấy file Excel (.xlsx / .xlsm) nào tại: {args.path}")
        sys.exit(1)

    print(f"[SEARCH] Tìm thấy {len(target_files)} file Excel cần xử lý.")

    summary = {
        "files_total": len(target_files),
        "files_imported": 0,
        "files_skipped": 0,
        "files_failed": 0,
        "total_vouchers": 0,
        "imported_vouchers": 0,
        "skipped_existing_vouchers": 0,
        "sellers_created": 0,
    }

    for idx, fpath in enumerate(target_files, 1):
        print(f"\n[{idx}/{len(target_files)}] Xử lý file: {fpath}")
        try:
            res = import_file(str(fpath), created_by_username=args.user, dry_run=args.dry_run, force=args.force)
            if res.get("status") == "skipped":
                print(f"  [SKIP] BỎ QUA - File đã được import trước đó ({res['file']})")
                summary["files_skipped"] += 1
            else:
                summary["files_imported"] += 1
                summary["total_vouchers"] += res["total"]
                summary["imported_vouchers"] += res["imported"]
                summary["skipped_existing_vouchers"] += res["skipped_existing"]
                summary["sellers_created"] += res["sellers_created"]
                print(f"  [OK] Tải xong: {res['imported']}/{res['total']} phiếu | Người bán mới: {res['sellers_created']}")
        except Exception as err:
            summary["files_failed"] += 1
            print(f"  [FAIL] LỖI khi xử lý file {fpath.name}: {err}")

    print("\n" + "=" * 50)
    print("[REPORT] BÁO CÁO KẾT QUẢ IMPORT EXCEL")
    print("=" * 50)
    print(f"• Tổng số file quét thấy:    {summary['files_total']}")
    print(f"• Số file đã import mới:      {summary['files_imported']}")
    print(f"• Số file đã bỏ qua (đã có): {summary['files_skipped']}")
    print(f"• Số file bị lỗi:            {summary['files_failed']}")
    print(f"• Tổng số phiếu đã lưu DB:    {summary['imported_vouchers']}")
    print(f"• Số phiếu trùng (bỏ qua):    {summary['skipped_existing_vouchers']}")
    print(f"• Số người bán mới tạo:      {summary['sellers_created']}")
    if args.dry_run:
        print("\n[WARN] CHẾ ĐỘ DRY-RUN: Không có dữ liệu nào thực sự được ghi vào DB.")
    print("=" * 50)


if __name__ == "__main__":
    main()
