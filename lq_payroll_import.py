"""
Payroll & attendance import — AGLog, salary sheets, attendance details, manual adjustments.
"""
from __future__ import annotations

import csv
import io
import json
import re
import secrets
import time
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

IMPORT_TYPES = ("aglog", "payroll_sheet", "attendance_detail", "manual_adjustments")
PREVIEW_TTL_SECONDS = 1800
IMPORT_PREVIEWS: Dict[str, Dict[str, Any]] = {}

AGLOG_LINE = re.compile(
    r"^(?P<no>\d+)\s+(?P<mchn>\d+)\s+(?P<enno>\d+)\s+(?P<name>\S*)\s+(?P<mode>\d+)\s+(?P<iomd>\d+)\s+(?P<dt>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s*$"
)

AR_DAY_NAMES = {
    "Saturday": "السبت",
    "Sunday": "الأحد",
    "Monday": "الاثنين",
    "Tuesday": "الثلاثاء",
    "Wednesday": "الأربعاء",
    "Thursday": "الخميس",
    "Friday": "الجمعة",
}


def uid(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def cleanup_import_previews() -> None:
    now_ts = time.time()
    expired = [k for k, v in IMPORT_PREVIEWS.items() if now_ts > float(v.get("expires_ts", 0))]
    for key in expired:
        IMPORT_PREVIEWS.pop(key, None)


def preview_key(username: str, preview_id: str) -> str:
    return f"{str(username or '').strip().lower()}::{str(preview_id or '').strip()}"


def normalize_employee_no(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.endswith(".0"):
        raw = raw[:-2]
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw
    return digits.zfill(9) if len(digits) <= 9 else digits


def parse_number(value: Any) -> float:
    if value is None:
        return 0.0
    raw = str(value).strip().replace(",", "")
    if not raw or raw in ("-", "—"):
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def normalize_month(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    m = re.match(r"^(\d{4})[-/](\d{1,2})$", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{1,2})[-/](\d{4})$", raw)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    return raw


def normalize_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def normalize_time(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?", raw)
    if not m:
        return raw
    sec = m.group(3) or "00"
    return f"{int(m.group(1)):02d}:{m.group(2)}:{sec}"


def decode_text_content(content: str, *, file_name: str = "") -> str:
    text = str(content or "")
    if not text.strip():
        return ""
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def sniff_delimiter(line: str) -> str:
    if "\t" in line:
        return "\t"
    if ";" in line and line.count(";") >= line.count(","):
        return ";"
    return ","


def parse_table_rows(content: str) -> List[Dict[str, str]]:
    text = decode_text_content(content)
    if not text.strip():
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    delimiter = sniff_delimiter(lines[0])
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    rows: List[Dict[str, str]] = []
    for row in reader:
        cleaned = {str(k or "").strip(): str(v or "").strip() for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


def header_aliases() -> Dict[str, Tuple[str, ...]]:
    return {
        "employee_no": (
            "employee_no",
            "employee id",
            "employee number",
            "enno",
            "رقم الموظف",
            "الرقم",
            "رقم",
        ),
        "employee_name": ("employee_name", "name", "الاسم", "اسم الموظف"),
        "basic_salary": ("basic_salary", "basic", "الراتب الأساسي", "الاساسي", "أساسي"),
        "allowances": ("allowances", "allowance", "البدلات", "بدلات"),
        "deductions": ("deductions", "deduction", "السلف/الخصومات", "الخصومات", "سلف"),
        "net_salary": ("net_salary", "net", "صافي الراتب", "الصافي", "صافي"),
        "work_date": ("work_date", "date", "التاريخ", "تاريخ"),
        "day_name": ("day_name", "day", "اليوم", "يوم"),
        "shift_type": ("shift_type", "shift", "نوع الدوام", "الدوام"),
        "attendance_status": ("attendance_status", "status", "الحالة", "حالة الحضور"),
        "action_type": ("action_type", "action", "نوع الإجراء", "الإجراء"),
        "scheduled_time": ("scheduled_time", "scheduled", "الوقت المجدول", "مجدول"),
        "actual_time": ("actual_time", "actual", "الوقت الفعلي", "فعلي", "البصمة"),
        "remarks": ("remarks", "notes", "ملاحظات", "الملاحظات", "حالة البصمة"),
        "adjustment_type": ("adjustment_type", "type", "نوع التعديل"),
        "value_before": ("value_before", "before", "قبل"),
        "value_after": ("value_after", "after", "بعد"),
        "adjusted_at": ("adjusted_at", "adjustment_time", "وقت التعديل"),
    }


def map_row_fields(row: Dict[str, str]) -> Dict[str, str]:
    aliases = header_aliases()
    normalized_headers = {re.sub(r"\s+", " ", k.strip().lower()): k for k in row.keys()}
    mapped: Dict[str, str] = {}
    for canonical, names in aliases.items():
        for name in names:
            key = normalized_headers.get(name.lower())
            if key and row.get(key):
                mapped[canonical] = row[key]
                break
    if not mapped:
        values = list(row.values())
        keys = list(row.keys())
        if len(keys) >= 2 and not any(ch.isalpha() for ch in "".join(keys[:3])):
            order = ["employee_no", "employee_name", "work_date", "day_name", "shift_type", "attendance_status", "action_type", "scheduled_time", "actual_time", "remarks"]
            for idx, field in enumerate(order):
                if idx < len(values):
                    mapped[field] = values[idx]
    return mapped


def parse_aglog(content: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    employees: Dict[str, str] = {}
    dates: set[str] = set()
    for line_no, line in enumerate(decode_text_content(content).splitlines(), start=1):
        line = line.strip()
        if not line or line.lower().startswith("no\t") or line.lower().startswith("no "):
            continue
        match = AGLOG_LINE.match(line)
        if not match:
            parts = re.split(r"\s+", line)
            if len(parts) >= 7 and parts[0].isdigit():
                dt_raw = " ".join(parts[6:8]) if len(parts) >= 8 else parts[6]
                match_data = {
                    "no": parts[0],
                    "mchn": parts[1],
                    "enno": parts[2],
                    "name": parts[3],
                    "mode": parts[4],
                    "iomd": parts[5],
                    "dt": dt_raw,
                }
            else:
                if line_no <= 3:
                    continue
                errors.append(f"سطر {line_no}: تنسيق غير معروف")
                continue
        else:
            match_data = match.groupdict()
        employee_no = normalize_employee_no(match_data["enno"])
        employee_name = str(match_data.get("name") or "").strip()
        if employee_no:
            employees[employee_no] = employee_name or employees.get(employee_no, "")
        dt_raw = str(match_data["dt"]).strip()
        try:
            punch_dt = datetime.strptime(dt_raw, "%Y/%m/%d %H:%M:%S")
        except ValueError:
            errors.append(f"سطر {line_no}: تاريخ غير صالح ({dt_raw})")
            continue
        punch_date = punch_dt.strftime("%Y-%m-%d")
        dates.add(punch_date)
        rows.append(
            {
                "record_no": str(match_data["no"]),
                "machine_no": int(match_data["mchn"]),
                "employee_no": employee_no,
                "employee_name": employee_name,
                "mode": int(match_data["mode"]),
                "io_mode": int(match_data["iomd"]),
                "punch_datetime": punch_dt.isoformat(sep=" "),
                "punch_date": punch_date,
                "punch_time": punch_dt.strftime("%H:%M:%S"),
            }
        )
    summary = {
        "parsed_rows": len(rows),
        "employee_count": len(employees),
        "date_from": min(dates) if dates else None,
        "date_to": max(dates) if dates else None,
        "errors": errors[:20],
        "error_count": len(errors),
        "employees_preview": [{"employee_no": k, "employee_name": v} for k, v in list(employees.items())[:12]],
    }
    return rows, summary


def parse_payroll_sheet(content: str, *, salary_month: str = "", project_name: str = "") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    table_rows = parse_table_rows(content)
    rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    month = normalize_month(salary_month)
    for idx, raw in enumerate(table_rows, start=1):
        mapped = map_row_fields(raw)
        employee_no = normalize_employee_no(mapped.get("employee_no"))
        employee_name = str(mapped.get("employee_name") or "").strip()
        if not employee_name and not employee_no:
            warnings.append(f"صف {idx}: بدون اسم أو رقم موظف")
            continue
        basic = parse_number(mapped.get("basic_salary"))
        allowances = parse_number(mapped.get("allowances"))
        deductions = parse_number(mapped.get("deductions"))
        net = parse_number(mapped.get("net_salary"))
        if net <= 0:
            net = round(basic + allowances - deductions, 3)
        rows.append(
            {
                "employee_no": employee_no,
                "employee_name": employee_name,
                "salary_month": month,
                "project_name": project_name,
                "basic_salary": basic,
                "allowances": allowances,
                "deductions": deductions,
                "net_salary": net,
            }
        )
    total_net = round(sum(r["net_salary"] for r in rows), 3)
    summary = {
        "parsed_rows": len(rows),
        "salary_month": month,
        "project_name": project_name,
        "total_net": total_net,
        "warnings": warnings[:20],
        "warning_count": len(warnings),
        "preview_rows": rows[:15],
    }
    return rows, summary


def parse_attendance_detail(content: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    table_rows = parse_table_rows(content)
    rows: List[Dict[str, Any]] = []
    skipped_extra = 0
    employees: Dict[str, str] = {}
    for raw in table_rows:
        mapped = map_row_fields(raw)
        employee_no = normalize_employee_no(mapped.get("employee_no"))
        employee_name = str(mapped.get("employee_name") or "").strip()
        if employee_no:
            employees[employee_no] = employee_name or employees.get(employee_no, "")
        remarks = str(mapped.get("remarks") or "").strip()
        action_type = str(mapped.get("action_type") or "").strip()
        combined = f"{remarks} {action_type}"
        is_extra = any(x in combined for x in ("بصمة زائدة", "لا تدخل بالحس", "extra fingerprint"))
        if is_extra:
            skipped_extra += 1
        rows.append(
            {
                "employee_no": employee_no,
                "employee_name": employee_name,
                "work_date": normalize_date(mapped.get("work_date")),
                "day_name": mapped.get("day_name") or "",
                "shift_type": mapped.get("shift_type") or "",
                "attendance_status": mapped.get("attendance_status") or "",
                "action_type": action_type,
                "scheduled_time": normalize_time(mapped.get("scheduled_time")),
                "actual_time": normalize_time(mapped.get("actual_time")),
                "remarks": remarks,
                "is_extra_punch": 1 if is_extra else 0,
            }
        )
    summary = {
        "parsed_rows": len(rows),
        "employee_count": len(employees),
        "extra_punches": skipped_extra,
        "preview_rows": rows[:20],
    }
    return rows, summary


def parse_manual_adjustments(content: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    table_rows = parse_table_rows(content)
    rows: List[Dict[str, Any]] = []
    for raw in table_rows:
        mapped = map_row_fields(raw)
        rows.append(
            {
                "employee_no": normalize_employee_no(mapped.get("employee_no")),
                "employee_name": str(mapped.get("employee_name") or "").strip(),
                "work_date": normalize_date(mapped.get("work_date")),
                "adjustment_type": mapped.get("adjustment_type") or "",
                "value_before": mapped.get("value_before") or "",
                "value_after": mapped.get("value_after") or "",
                "adjusted_at": mapped.get("adjusted_at") or "",
            }
        )
    summary = {
        "parsed_rows": len(rows),
        "preview_rows": rows[:20],
    }
    return rows, summary


def build_preview(
    import_type: str,
    content: str,
    *,
    file_name: str = "",
    salary_month: str = "",
    project_name: str = "",
) -> Dict[str, Any]:
    if import_type not in IMPORT_TYPES:
        raise ValueError("نوع الاستيراد غير مدعوم")
    text = decode_text_content(content, file_name=file_name)
    if not text.strip():
        raise ValueError("الملف فارغ")
    if import_type == "aglog":
        rows, summary = parse_aglog(text)
    elif import_type == "payroll_sheet":
        rows, summary = parse_payroll_sheet(text, salary_month=salary_month, project_name=project_name)
    elif import_type == "attendance_detail":
        rows, summary = parse_attendance_detail(text)
    else:
        rows, summary = parse_manual_adjustments(text)
    if not rows:
        raise ValueError("لم يتم العثور على سجلات صالحة للاستيراد")
    preview_id = uid("PI")
    payload = {
        "preview_id": preview_id,
        "import_type": import_type,
        "file_name": file_name,
        "salary_month": normalize_month(salary_month),
        "project_name": project_name,
        "rows": rows,
        "summary": summary,
        "created_at": now_iso(),
        "expires_ts": time.time() + PREVIEW_TTL_SECONDS,
    }
    return payload


def store_preview(username: str, payload: Dict[str, Any]) -> str:
    cleanup_import_previews()
    preview_id = str(payload["preview_id"])
    IMPORT_PREVIEWS[preview_key(username, preview_id)] = payload
    return preview_id


def load_preview(username: str, preview_id: str) -> Dict[str, Any]:
    cleanup_import_previews()
    item = IMPORT_PREVIEWS.get(preview_key(username, preview_id))
    if not item:
        raise ValueError("انتهت صلاحية المعاينة — أعد رفع الملف")
    return item


def pop_preview(username: str, preview_id: str) -> Dict[str, Any]:
    item = load_preview(username, preview_id)
    IMPORT_PREVIEWS.pop(preview_key(username, preview_id), None)
    return item


def commit_preview(
    db: Any,
    user: Dict[str, Any],
    preview: Dict[str, Any],
    *,
    insert_fn: Callable[..., None],
    uid_fn: Callable[[str], str],
    today_fn: Callable[[], str],
) -> Dict[str, Any]:
    import_type = preview["import_type"]
    rows = preview.get("rows") or []
    batch_id = uid_fn("BATCH")
    created_by = str(user.get("username") or user.get("name") or "system")
    summary = dict(preview.get("summary") or {})
    committed = 0

    insert_fn(
        db,
        "payroll_import_batches",
        {
            "id": batch_id,
            "import_type": import_type,
            "file_name": preview.get("file_name") or "",
            "project_name": preview.get("project_name") or "",
            "salary_month": preview.get("salary_month") or "",
            "status": "committed",
            "row_count": len(rows),
            "summary_json": json.dumps(summary, ensure_ascii=False),
            "created_by": created_by,
            "created_at": now_iso(),
        },
    )

    if import_type == "aglog":
        for row in rows:
            insert_fn(
                db,
                "attendance_punches",
                {
                    "id": uid_fn("PUNCH"),
                    "batch_id": batch_id,
                    "record_no": row.get("record_no"),
                    "machine_no": row.get("machine_no"),
                    "employee_no": row.get("employee_no"),
                    "employee_name": row.get("employee_name"),
                    "mode": row.get("mode"),
                    "io_mode": row.get("io_mode"),
                    "punch_datetime": row.get("punch_datetime"),
                    "punch_date": row.get("punch_date"),
                    "punch_time": row.get("punch_time"),
                    "source": "aglog",
                },
            )
            committed += 1

    elif import_type == "payroll_sheet":
        salary_month = preview.get("salary_month") or today_fn()[:7]
        project_name = preview.get("project_name") or ""
        for row in rows:
            net = float(row.get("net_salary") or 0)
            acc_id = uid_fn("ACC")
            insert_fn(
                db,
                "accounts",
                {
                    "id": acc_id,
                    "entry_date": today_fn(),
                    "type": "expense",
                    "category": "Payroll",
                    "description": f"Salary {row.get('employee_name')} {salary_month}",
                    "client_id": None,
                    "property_id": None,
                    "invoice_id": None,
                    "amount": net,
                },
            )
            insert_fn(
                db,
                "salaries",
                {
                    "id": uid_fn("SAL"),
                    "employee_no": row.get("employee_no"),
                    "employee_name": row.get("employee_name"),
                    "salary_month": row.get("salary_month") or salary_month,
                    "project_name": row.get("project_name") or project_name,
                    "basic_salary": row.get("basic_salary"),
                    "allowances": row.get("allowances"),
                    "deductions": row.get("deductions"),
                    "net_salary": net,
                    "status": "Pending",
                    "payment_date": today_fn(),
                    "account_id": acc_id,
                    "import_batch_id": batch_id,
                },
            )
            committed += 1

    elif import_type == "attendance_detail":
        for row in rows:
            insert_fn(
                db,
                "attendance_days",
                {
                    "id": uid_fn("ADAY"),
                    "batch_id": batch_id,
                    "employee_no": row.get("employee_no"),
                    "employee_name": row.get("employee_name"),
                    "work_date": row.get("work_date"),
                    "day_name": row.get("day_name"),
                    "shift_type": row.get("shift_type"),
                    "attendance_status": row.get("attendance_status"),
                    "action_type": row.get("action_type"),
                    "scheduled_time": row.get("scheduled_time"),
                    "actual_time": row.get("actual_time"),
                    "remarks": row.get("remarks"),
                    "is_extra_punch": row.get("is_extra_punch") or 0,
                },
            )
            committed += 1

    else:
        for row in rows:
            insert_fn(
                db,
                "attendance_adjustments",
                {
                    "id": uid_fn("ADJ"),
                    "batch_id": batch_id,
                    "employee_no": row.get("employee_no"),
                    "employee_name": row.get("employee_name"),
                    "work_date": row.get("work_date"),
                    "adjustment_type": row.get("adjustment_type"),
                    "value_before": row.get("value_before"),
                    "value_after": row.get("value_after"),
                    "adjusted_at": row.get("adjusted_at"),
                    "created_at": now_iso(),
                },
            )
            committed += 1

    return {
        "batch_id": batch_id,
        "import_type": import_type,
        "committed_rows": committed,
        "summary": summary,
    }
