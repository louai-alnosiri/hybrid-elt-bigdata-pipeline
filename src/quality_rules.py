"""
═══════════════════════════════════════════════════════════════════
قواعد التنظيف التسع وأكواد العزل الجوهرية (src/quality_rules.py)
───────────────────────────────────────────────────────────────────
توثيق وتنفيذ قواعد جودة البيانات التسع (9 Rules) مع Audit Trail كامل.
تعريف رموز العزل الجوهرية (Quarantine Codes) وفحوصات السلامة.
═══════════════════════════════════════════════════════════════════
"""

import json
import re
import logging
from datetime import datetime, timezone

from config.settings import PHONE_COUNTRY_CODE, TARGET_CURRENCY

logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════╗
# ║                   رموز أسباب العزل (Quarantine)             ║
# ╚══════════════════════════════════════════════════════════════╝

QUARANTINE_CODES = {
    "ID_ORDER_MISSING":         "معرّف الطلب (order_id) فارغ أو مفقود",
    "ID_CUSTOMER_MISSING":      "معرّف العميل (customer_id) فارغ أو مفقود",
    "DATE_IMPOSSIBLE_INVALID":  "تاريخ غير صالح ولا يمكن تحويله إلى صيغة معروفة",
    "JSON_ITEMS_CORRUPTED":     "حقل items_json تالف ولا يمكن تحليله كـ JSON",
    "ITEMS_EMPTY":              "قائمة العناصر فارغة بعد التحليل",
    "PRICE_UNKNOWN":            "سعر غير قابل للتحليل (??? أو قيمة غير رقمية بعد التنظيف)",
    "VALUE_NEGATIVE_AMBIGUOUS": "قيمة سالبة أو ملتبسة في كمية أو سعر عنصر",
}

_ARABIC_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def _try_parse_numeric(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.translate(_ARABIC_DIGIT_MAP)
    s = s.replace(",", "")
    for word in ("ريال", "ر.ي", "يمني", "YER"):
        s = s.replace(word, "")
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _try_parse_json_items(items_json_str):
    if not items_json_str or not items_json_str.strip():
        return None, "JSON_ITEMS_CORRUPTED"
    try:
        items = json.loads(items_json_str.strip())
        if not isinstance(items, list):
            return None, "JSON_ITEMS_CORRUPTED"
        if len(items) == 0:
            return None, "ITEMS_EMPTY"
        return items, None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, "JSON_ITEMS_CORRUPTED"


def check_fatal_quarantine(record, enabled_quarantines=None):
    """فحص الأخطاء الجوهرية قبل تطبيق أي قاعدة تنظيف مع دعم الفلترة الديناميكية."""
    eq = enabled_quarantines or {}
    check_all = enabled_quarantines is None

    order_id = (record.get("order_id") or "").strip()
    if (check_all or eq.get("q_order_id", True)) and not order_id:
        return "ID_ORDER_MISSING", QUARANTINE_CODES["ID_ORDER_MISSING"]

    customer_id = (record.get("customer_id") or "").strip()
    if (check_all or eq.get("q_customer_id", True)) and not customer_id:
        return "ID_CUSTOMER_MISSING", QUARANTINE_CODES["ID_CUSTOMER_MISSING"]

    date_str = (record.get("order_date") or "").strip()
    if (check_all or eq.get("q_date", True)) and (not date_str or not re.search(r"[\d٠-٩]", date_str)):
        return "DATE_IMPOSSIBLE_INVALID", QUARANTINE_CODES["DATE_IMPOSSIBLE_INVALID"]

    items_json_str = (record.get("items_json") or "").strip()
    items, error_code = _try_parse_json_items(items_json_str)
    if error_code:
        if error_code == "JSON_ITEMS_CORRUPTED" and (check_all or eq.get("q_items_json", True)):
            return error_code, QUARANTINE_CODES[error_code]
        elif error_code == "ITEMS_EMPTY" and (check_all or eq.get("q_items_empty", True)):
            return error_code, QUARANTINE_CODES[error_code]

    if items:
        for item in items:
            qty_val = item.get("qty")
            price_val = item.get("unit_price")

            qty_num = _try_parse_numeric(qty_val)
            if (check_all or eq.get("q_negative", True)) and qty_num is not None and qty_num < 0:
                return "VALUE_NEGATIVE_AMBIGUOUS", QUARANTINE_CODES["VALUE_NEGATIVE_AMBIGUOUS"]

            price_num = _try_parse_numeric(price_val)
            if (check_all or eq.get("q_negative", True)) and price_num is not None and price_num < 0:
                return "VALUE_NEGATIVE_AMBIGUOUS", QUARANTINE_CODES["VALUE_NEGATIVE_AMBIGUOUS"]

            if (check_all or eq.get("q_price_unknown", True)) and price_val is not None and price_num is None:
                if str(price_val).strip():
                    return "PRICE_UNKNOWN", QUARANTINE_CODES["PRICE_UNKNOWN"]

    if check_all or eq.get("q_price_unknown", True):
        for field_name in ("payment_amount", "total_amount", "delivery_cost"):
            val = (record.get(field_name) or "").strip()
            if val:
                num = _try_parse_numeric(val)
                if num is None:
                    return "PRICE_UNKNOWN", QUARANTINE_CODES["PRICE_UNKNOWN"]

    return None


def check_post_cleaning_quarantine(record, enabled_quarantines=None):
    """فحص ما بعد التنظيف للتأكد من المخرجات مع دعم الفلترة الديناميكية."""
    eq = enabled_quarantines or {}
    check_all = enabled_quarantines is None

    date_str = (record.get("order_date") or "").strip()
    if (check_all or eq.get("q_date", True)) and date_str:
        try:
            datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return "DATE_IMPOSSIBLE_INVALID", QUARANTINE_CODES["DATE_IMPOSSIBLE_INVALID"]

    if check_all or eq.get("q_price_unknown", True):
        for field_name in ("delivery_cost", "payment_amount", "total_amount"):
            val = (record.get(field_name) or "").strip()
            if val:
                try:
                    float(val)
                except (ValueError, TypeError):
                    return "PRICE_UNKNOWN", QUARANTINE_CODES["PRICE_UNKNOWN"]

    return None


def build_quarantine_doc(record, error_code, run_id):
    """بناء مستند العزل completo."""
    original = {k: v for k, v in record.items() if k != "_id"}
    return {
        "order_id": (record.get("order_id") or f"__MISSING_{id(record)}__").strip(),
        "error_code": error_code,
        "error_reason": QUARANTINE_CODES.get(error_code, "خطأ غير معروف"),
        "original_record": original,
        "quarantined_at": datetime.utcnow().isoformat(),
        "run_id": run_id,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║                   قواعد التنظيف التسع (9 Rules)            ║
# ╚══════════════════════════════════════════════════════════════╝

def rule_arabic_numerals(value):
    """1. تحويل الأرقام العربية إلى لاتينية."""
    if not value or not isinstance(value, str):
        return value, None
    has_arabic = any(c in "٠١٢٣٤٥٦٧٨٩٫" for c in value)
    if not has_arabic:
        return value, None
    original = value
    cleaned = value.translate(_ARABIC_DIGIT_MAP)
    return cleaned, {
        "rule_code": "ARABIC_NUMERALS",
        "original_value": original,
        "corrected_value": cleaned,
    }


_CURRENCY_PATTERNS = [r"\s*ريال\s*يمني\s*", r"\s*ريال\s*", r"\s*ر\.ي\.?\s*", r"\s*يمني\s*", r"\s*YER\s*"]
_CURRENCY_RE = re.compile("|".join(_CURRENCY_PATTERNS))


def rule_currency_normalize_amount(value):
    """2. إزالة نصوص العملة من المبالغ."""
    if not value or not isinstance(value, str):
        return value, None
    cleaned = _CURRENCY_RE.sub("", value).strip()
    if cleaned == value.strip():
        return value, None
    return cleaned, {
        "rule_code": "CURRENCY_NORMALIZE",
        "original_value": value,
        "corrected_value": cleaned,
    }


def rule_currency_normalize_field(value):
    """2. توحيد رمز العملة إلى YER."""
    if not value or not isinstance(value, str):
        return TARGET_CURRENCY, None
    stripped = value.strip()
    if stripped == TARGET_CURRENCY:
        return stripped, None
    return TARGET_CURRENCY, {
        "rule_code": "CURRENCY_NORMALIZE",
        "original_value": value,
        "corrected_value": TARGET_CURRENCY,
    }


_THOUSANDS_RE = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


def rule_thousands_separator(value):
    """3. إزالة فواصل الآلاف."""
    if not value or not isinstance(value, str):
        return value, None
    stripped = value.strip()
    if "," not in stripped:
        return value, None
    if _THOUSANDS_RE.match(stripped):
        original = value
        cleaned = stripped.replace(",", "")
        return cleaned, {
            "rule_code": "THOUSANDS_SEPARATOR",
            "original_value": original,
            "corrected_value": cleaned,
        }
    return value, None


_WORD_NUMBERS = {
    "مئة": 100, "مائة": 100, "مئتان": 200, "مائتان": 200, "مئتين": 200, "مائتين": 200,
    "ثلاثمئة": 300, "ثلاثمائة": 300, "أربعمئة": 400, "أربعمائة": 400, "خمسمئة": 500, "خمسمائة": 500,
    "ستمئة": 600, "ستمائة": 600, "سبعمئة": 700, "سبعمائة": 700, "ثمانمئة": 800, "ثمانمائة": 800,
    "تسعمئة": 900, "تسعمائة": 900, "ألف": 1000, "ألفان": 2000, "ألفين": 2000,
    "ثلاثة آلاف": 3000, "أربعة آلاف": 4000, "خمسة آلاف": 5000, "ستة آلاف": 6000,
    "سبعة آلاف": 7000, "ثمانية آلاف": 8000, "تسعة آلاف": 9000, "عشرة آلاف": 10000,
    "مليون": 1000000, "نصف مليون": 500000,
}
_SORTED_WORD_NUMBERS = sorted(_WORD_NUMBERS.items(), key=lambda x: -len(x[0]))


def rule_word_to_number(value):
    """4. تحويل الأسعار المكتوبة بالكلمات."""
    if not value or not isinstance(value, str):
        return value, None
    stripped = value.strip()
    try:
        float(stripped)
        return value, None
    except (ValueError, TypeError):
        pass

    remaining = re.sub(r"\s*و\s*", " ", stripped).strip()
    total = 0
    found = False

    for word, num in _SORTED_WORD_NUMBERS:
        if word in remaining:
            total += num
            remaining = remaining.replace(word, "", 1).strip()
            found = True

    if found and (not remaining or remaining in ("", "و")):
        cleaned = str(total)
        return cleaned, {
            "rule_code": "WORD_TO_NUMBER",
            "original_value": value,
            "corrected_value": cleaned,
        }
    return value, None


def rule_phone_normalize(value):
    """5. توحيد صيغة الهواتف والتنسيق الدولي."""
    if not value or not isinstance(value, str):
        return value, None
    original = value
    cleaned = re.sub(r"[\s\-\(\)]+", "", value.strip())

    if cleaned.startswith("00967"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("967") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    if re.match(r"^7\d{8}$", cleaned):
        cleaned = PHONE_COUNTRY_CODE + cleaned

    if cleaned == original.strip():
        return value, None

    return cleaned, {
        "rule_code": "PHONE_NORMALIZE",
        "original_value": original,
        "corrected_value": cleaned,
    }


def rule_email_fix(value):
    """6. تصحيح تكرار رموز البريد."""
    if not value or not isinstance(value, str):
        return value, None
    original = value
    cleaned = value.strip()

    while "@@" in cleaned:
        cleaned = cleaned.replace("@@", "@")

    if "@" in cleaned:
        local_part, domain = cleaned.rsplit("@", 1)
        while ".." in domain:
            domain = domain.replace("..", ".")
        cleaned = f"{local_part}@{domain}"

    cleaned = cleaned.replace(" ", "")

    if cleaned == original.strip():
        return value, None

    return cleaned, {
        "rule_code": "EMAIL_FIX",
        "original_value": original,
        "corrected_value": cleaned,
    }


_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
    "%d-%m-%Y %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y",
]


def rule_date_normalize(value):
    """7. توحيد التواريخ إلى ISO Format."""
    if not value or not isinstance(value, str):
        return value, None
    stripped = value.strip().translate(_ARABIC_DIGIT_MAP)

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(stripped, fmt)
            iso_str = dt.strftime("%Y-%m-%dT%H:%M:%S")
            if dt.year < 1900 or dt.year > 2100:
                continue
            if iso_str == value.strip():
                return value, None
            return iso_str, {
                "rule_code": "DATE_NORMALIZE",
                "original_value": value,
                "corrected_value": iso_str,
            }
        except ValueError:
            continue
    return value, None


def rule_text_normalize(value, field_name="status"):
    """8. إزالة المسافات الزائدة وتوحيد النصوص."""
    if not value or not isinstance(value, str):
        return value, None
    original = value
    cleaned = " ".join(value.split())
    if cleaned == original:
        return value, None
    return cleaned, {
        "rule_code": "TEXT_NORMALIZE",
        "original_value": original,
        "corrected_value": cleaned,
    }


def rule_total_recalc(record, items):
    """9. إعادة حساب المطابقة الإجمالية."""
    try:
        delivery_cost = float(record.get("delivery_cost", 0))
        items_total = sum(float(item.get("total", 0)) for item in items)
        expected_total = items_total + delivery_cost

        current_total_str = record.get("total_amount", "0")
        current_total = float(current_total_str)

        if abs(current_total - expected_total) > 0.01:
            corrected = str(expected_total)
            return corrected, {
                "rule_code": "TOTAL_RECALC",
                "original_value": current_total_str,
                "corrected_value": corrected,
            }
        return current_total_str, None
    except (ValueError, TypeError):
        return record.get("total_amount", "0"), None


def _apply_numeric_rules(value, field_name, corrections):
    value, audit = rule_arabic_numerals(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    value, audit = rule_currency_normalize_amount(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    value, audit = rule_thousands_separator(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    value, audit = rule_word_to_number(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    return value


def apply_all_rules(record, enabled_rules=None):
    """تطبيق القواعد على السجل مع دعم التفعيل والتعطيل الديناميكي لكل قاعدة."""
    er = enabled_rules or {}
    apply_all = enabled_rules is None

    record = dict(record)
    corrections = []

    if apply_all or er.get("rule_numeric", True):
        for field in ("delivery_cost", "payment_amount", "total_amount"):
            val = record.get(field, "") or ""
            cleaned = _apply_numeric_rules(val, field, corrections)
            record[field] = cleaned

    if apply_all or er.get("rule_currency", True):
        currency_val = record.get("currency", "") or ""
        cleaned_currency, audit = rule_currency_normalize_field(currency_val)
        if audit:
            audit["field"] = "currency"
            corrections.append(audit)
        record["currency"] = cleaned_currency

    if apply_all or er.get("rule_phone", True):
        phone_val = record.get("customer_phone", "") or ""
        cleaned_phone, audit = rule_phone_normalize(phone_val)
        if audit:
            audit["field"] = "customer_phone"
            corrections.append(audit)
        record["customer_phone"] = cleaned_phone

    if apply_all or er.get("rule_email", True):
        email_val = record.get("customer_email", "") or ""
        cleaned_email, audit = rule_email_fix(email_val)
        if audit:
            audit["field"] = "customer_email"
            corrections.append(audit)
        record["customer_email"] = cleaned_email

    if apply_all or er.get("rule_date", True):
        date_val = record.get("order_date", "") or ""
        cleaned_date, audit = rule_date_normalize(date_val)
        if audit:
            audit["field"] = "order_date"
            corrections.append(audit)
        record["order_date"] = cleaned_date

    if apply_all or er.get("rule_text", True):
        for field in ("status", "customer_name", "city", "district",
                      "delivery_type", "payment_method", "payment_status"):
            val = record.get(field, "") or ""
            cleaned_text, audit = rule_text_normalize(val, field)
            if audit:
                audit["field"] = field
                corrections.append(audit)
            record[field] = cleaned_text

    items_json_str = record.get("items_json", "") or "[]"
    try:
        items = json.loads(items_json_str) if isinstance(items_json_str, str) else items_json_str
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []

    if (apply_all or er.get("rule_items", True)) and items:
        for idx, item in enumerate(items):
            for item_field in ("unit_price", "total", "qty"):
                raw_val = item.get(item_field)
                if raw_val is None:
                    continue
                str_val = str(raw_val)
                cleaned = _apply_numeric_rules(str_val, f"items[{idx}].{item_field}", corrections)
                try:
                    item[item_field] = float(cleaned) if "." in cleaned else int(cleaned)
                except (ValueError, TypeError):
                    item[item_field] = cleaned

    if (apply_all or er.get("rule_total_recalc", True)) and items:
        corrected_total, audit = rule_total_recalc(record, items)
        if audit:
            audit["field"] = "total_amount"
            corrections.append(audit)
        record["total_amount"] = corrected_total

    record["items_json"] = json.dumps(items, ensure_ascii=False)

    return record, items, corrections


def build_quarantine_doc(record, error_code, run_id):
    """بناء مستند العزل لكولكشن orders_quarantine."""
    return {
        "order_id": str(record.get("order_id", "")).strip(),
        "run_id": run_id,
        "quarantine_reason": error_code,
        "error_codes": [error_code],
        "error_details": f"فشل التحقق: {error_code}",
        "raw_record": record,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_validated_doc(cleaned_record, items, corrections, run_id):
    """بناء المستند الموثق لكولكشن orders_validated."""
    return {
        "order_id": str(cleaned_record.get("order_id", "")).strip(),
        "run_id": run_id,
        "customer_id": str(cleaned_record.get("customer_id", "")).strip(),
        "customer_name": cleaned_record.get("customer_name", ""),
        "customer_phone": cleaned_record.get("customer_phone", ""),
        "customer_email": cleaned_record.get("customer_email", ""),
        "order_date": cleaned_record.get("order_date", ""),
        "status": cleaned_record.get("status", ""),
        "city": cleaned_record.get("city", ""),
        "district": cleaned_record.get("district", ""),
        "delivery_type": cleaned_record.get("delivery_type", ""),
        "delivery_cost": float(cleaned_record.get("delivery_cost", 0) or 0),
        "payment_method": cleaned_record.get("payment_method", ""),
        "payment_status": cleaned_record.get("payment_status", ""),
        "payment_amount": float(cleaned_record.get("payment_amount", 0) or 0),
        "currency": cleaned_record.get("currency", "YER"),
        "total_amount": float(cleaned_record.get("total_amount", 0) or 0),
        "items": items,
        "quality_status": "corrected" if corrections else "valid",
        "corrections": corrections,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

