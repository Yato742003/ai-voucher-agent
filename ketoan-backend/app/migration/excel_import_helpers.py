"""
Helper constants and functions for importing Excel voucher files.
"""
import re
from datetime import datetime, date
from pathlib import Path

from sqlalchemy import select

from app.models.setting import AppSetting
from app.models.audit_log import AuditLog

TITLE_COL = 20
NAME_COL = 1
NAME_ROW_OFFSET = 7
ADDRESS_ROW_OFFSET = 8
REASON_ROW_OFFSET = 9
AMOUNT_ROW_OFFSET = 10
AMOUNT_COL = 6
TITLE_ROW_OFFSET = 3
SO_PHIEU_COL = 54
SO_PHIEU_ROW_OFFSET = 4
DATE_COL = 20
DATE_ROW_OFFSET = 4

_DATE_RE = re.compile(r"Ngày\s*(\d+)\s*tháng\s*(\d+)\s*năm\s*(\d+)")


def label_value(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.split(":", 1)[1].strip() if ":" in raw else raw.strip()


def parse_date(raw) -> date | None:
    if isinstance(raw, date):
        return raw
    if not raw:
        return None
    m = _DATE_RE.search(str(raw))
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def get_target_sheet(wb):
    for name in ["LUU", "LƯU", "Luu", "luu"]:
        if name in wb.sheetnames:
            return wb[name]
    for name in wb.sheetnames:
        if "LUU" in name.upper() or "LƯU" in name.upper():
            return wb[name]
    if len(wb.sheetnames) == 1:
        return wb.active
    raise ValueError(f"Không tìm thấy sheet 'LUU' trong file. Danh sách sheet hiện có: {wb.sheetnames}")


def detect_blocks(ws):
    title_rows = []
    for r in range(1, ws.max_row + 1):
        v = ws.cell(row=r, column=TITLE_COL).value
        if v and "PHIẾU CHI" in str(v).upper():
            title_rows.append(r)

    if len(title_rows) < 2:
        title_rows = []
        for r in range(1, ws.max_row + 1):
            for c in range(1, min(ws.max_column + 1, 60)):
                v = ws.cell(row=r, column=c).value
                if v and "PHIẾU CHI" in str(v).upper():
                    title_rows.append(r)
                    break

    if len(title_rows) < 2:
        raise ValueError("Không tìm đủ block 'PHIẾU CHI' trong sheet Excel")

    diffs = {title_rows[i + 1] - title_rows[i] for i in range(len(title_rows) - 1)}
    if len(diffs) != 1:
        raise ValueError(f"Chiều cao block không đồng nhất giữa các phiếu: {diffs}")
    height = diffs.pop()
    starts = [r - TITLE_ROW_OFFSET for r in title_rows[1:]]
    return height, starts


def resolve_excel_files(path_input: str) -> list[Path]:
    p = Path(path_input)
    files: list[Path] = []

    if p.is_dir():
        for item in sorted(p.rglob("*")):
            if item.is_file() and not item.name.startswith("~$") and item.suffix.lower() in [".xlsx", ".xlsm"]:
                files.append(item)
    elif p.is_file():
        if not p.name.startswith("~$") and p.suffix.lower() in [".xlsx", ".xlsm"]:
            files.append(p)
    else:
        parent = p.parent if str(p.parent) != "" else Path(".")
        pattern = p.name
        if parent.exists():
            for item in sorted(parent.glob(pattern)):
                if item.is_file() and not item.name.startswith("~$") and item.suffix.lower() in [".xlsx", ".xlsm"]:
                    files.append(item)
                elif item.is_dir():
                    for sub in sorted(item.rglob("*")):
                        if sub.is_file() and not sub.name.startswith("~$") and sub.suffix.lower() in [".xlsx", ".xlsm"]:
                            files.append(sub)

    seen = set()
    unique_files = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    return unique_files


def is_file_imported(db, filename: str) -> bool:
    setting_key = f"imported_excel_file:{filename}"
    setting = db.execute(select(AppSetting).where(AppSetting.key == setting_key)).scalar_one_or_none()
    if setting is not None:
        return True

    log = db.execute(
        select(AuditLog).where(
            AuditLog.action == "import_from_excel",
            AuditLog.after_data["source_file"].astext == filename,
        )
    ).first()
    return log is not None


def mark_file_imported(db, filename: str):
    setting_key = f"imported_excel_file:{filename}"
    setting = db.execute(select(AppSetting).where(AppSetting.key == setting_key)).scalar_one_or_none()
    if setting is None:
        setting = AppSetting(key=setting_key, value=datetime.now().isoformat())
        db.add(setting)
    else:
        setting.value = datetime.now().isoformat()
