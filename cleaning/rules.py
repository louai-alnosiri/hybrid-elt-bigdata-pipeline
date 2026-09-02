"""
═══════════════════════════════════════════════════════════════════
قواعد التنظيف التسع (9 Cleaning Rules) مع أثر التصحيح (Audit Trail)
───────────────────────────────────────────────────────────────────
كل قاعدة تُرجع (cleaned_value, audit_entry | None).
audit_entry يحتوي:
  { field, rule_code, original_value, corrected_value }

القواعد:
  1. ARABIC_NUMERALS     — تحويل الأرقام العربية إلى لاتينية
  2. CURRENCY_NORMALIZE  — توحيد رمز واسم العملة
  3. THOUSANDS_SEPARATOR — إزالة فواصل الآلاف
  4. WORD_TO_NUMBER      — تحويل الأسعار المكتوبة بالكلمات
  5. PHONE_NORMALIZE     — توحيد صيغة أرقام الهواتف
  6. EMAIL_FIX           — تصحيح تكرار رموز البريد
  7. DATE_NORMALIZE      — توحيد صيغ التواريخ (ISO)
  8. TEXT_NORMALIZE       — إزالة المسافات وتوحيد حالة الطلب
  9. TOTAL_RECALC        — إعادة حساب إجمالي الطلب
═══════════════════════════════════════════════════════════════════
"""

import json
import re
import logging
from datetime import datetime

from config.settings import PHONE_COUNTRY_CODE, TARGET_CURRENCY

logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════╗
# ║          القاعدة 1: تحويل الأرقام العربية (ARABIC_NUMERALS) ║
# ╚══════════════════════════════════════════════════════════════╝

_ARABIC_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def rule_arabic_numerals(value):
    """
    تحويل الأرقام العربية (٠-٩) والفاصلة العشرية العربية (٫)
    إلى أرقام لاتينية (0-9) ونقطة عشرية (.).
    مثال: ٧٠٦٠٠٠٫٠ → 706000.0
    """
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


# ╔══════════════════════════════════════════════════════════════╗
# ║         القاعدة 2: توحيد العملة (CURRENCY_NORMALIZE)        ║
# ╚══════════════════════════════════════════════════════════════╝

_CURRENCY_PATTERNS = [
    r"\s*ريال\s*يمني\s*",
    r"\s*ريال\s*",
    r"\s*ر\.ي\.?\s*",
    r"\s*يمني\s*",
    r"\s*YER\s*",
]

_CURRENCY_RE = re.compile("|".join(_CURRENCY_PATTERNS))


def rule_currency_normalize_amount(value):
    """
    إزالة نصوص العملة من حقول المبالغ المالية.
    مثال: "54000.00 ريال" → "54000.00"
    """
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
    """
    توحيد حقل العملة نفسه إلى القيمة المعتمدة (YER).
    """
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


# ╔══════════════════════════════════════════════════════════════╗
# ║        القاعدة 3: إزالة فواصل الآلاف (THOUSANDS_SEPARATOR)  ║
# ╚══════════════════════════════════════════════════════════════╝

_THOUSANDS_RE = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")


def rule_thousands_separator(value):
    """
    إزالة فواصل الآلاف من الأرقام.
    مثال: "135,000.00" → "135000.00"
    """
    if not value or not isinstance(value, str):
        return value, None

    stripped = value.strip()
    if "," not in stripped:
        return value, None

    # التحقق أن الفواصل هي فعلاً فواصل آلاف (وليست جزء من نص)
    if _THOUSANDS_RE.match(stripped):
        original = value
        cleaned = stripped.replace(",", "")
        return cleaned, {
            "rule_code": "THOUSANDS_SEPARATOR",
            "original_value": original,
            "corrected_value": cleaned,
        }

    return value, None


# ╔══════════════════════════════════════════════════════════════╗
# ║       القاعدة 4: الأسعار بالكلمات (WORD_TO_NUMBER)          ║
# ╚══════════════════════════════════════════════════════════════╝

# قاموس الأعداد العربية بالكلمات → قيم رقمية
_WORD_NUMBERS = {
    # المئات
    "مئة": 100, "مائة": 100,
    "مئتان": 200, "مائتان": 200, "مئتين": 200, "مائتين": 200,
    "ثلاثمئة": 300, "ثلاثمائة": 300,
    "أربعمئة": 400, "أربعمائة": 400,
    "خمسمئة": 500, "خمسمائة": 500,
    "ستمئة": 600, "ستمائة": 600,
    "سبعمئة": 700, "سبعمائة": 700,
    "ثمانمئة": 800, "ثمانمائة": 800,
    "تسعمئة": 900, "تسعمائة": 900,
    # الآلاف
    "ألف": 1000,
    "ألفان": 2000, "ألفين": 2000,
    "ثلاثة آلاف": 3000, "ثلاثه آلاف": 3000,
    "أربعة آلاف": 4000, "أربعه آلاف": 4000,
    "خمسة آلاف": 5000, "خمسه آلاف": 5000,
    "ستة آلاف": 6000, "سته آلاف": 6000,
    "سبعة آلاف": 7000, "سبعه آلاف": 7000,
    "ثمانية آلاف": 8000, "ثمانيه آلاف": 8000,
    "تسعة آلاف": 9000, "تسعه آلاف": 9000,
    "عشرة آلاف": 10000, "عشره آلاف": 10000,
    # قيم كبيرة
    "مليون": 1000000,
    "نصف مليون": 500000,
}

# ترتيب حسب الطول (الأطول أولاً لتجنب التطابق الجزئي)
_SORTED_WORD_NUMBERS = sorted(_WORD_NUMBERS.items(), key=lambda x: -len(x[0]))


def rule_word_to_number(value):
    """
    تحويل الأسعار المكتوبة بالكلمات العربية إلى أرقام.
    مثال: "خمسة آلاف" → "5000"
    يدعم التركيب: "خمسة آلاف وخمسمائة" → "5500"
    """
    if not value or not isinstance(value, str):
        return value, None

    stripped = value.strip()
    # تجاهل إذا كانت القيمة رقمية بالفعل
    try:
        float(stripped)
        return value, None
    except (ValueError, TypeError):
        pass

    # محاولة التحويل: فحص النص كاملاً أو أجزاء منه
    remaining = stripped
    total = 0
    found = False

    # إزالة "و" الربط
    remaining = re.sub(r"\s*و\s*", " ", remaining).strip()

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


# ╔══════════════════════════════════════════════════════════════╗
# ║          القاعدة 5: توحيد الهواتف (PHONE_NORMALIZE)         ║
# ╚══════════════════════════════════════════════════════════════╝

def rule_phone_normalize(value):
    """
    توحيد صيغة أرقام الهواتف:
    - إزالة المسافات الزائدة
    - إضافة رمز الدولة +967 إذا مفقود
    - توحيد الصيغة
    
    مثال: "702390941" → "+967702390941"
    مثال: "+967 776678555" → "+967776678555"
    مثال: "00967712345678" → "+967712345678"
    """
    if not value or not isinstance(value, str):
        return value, None

    original = value
    # إزالة كل المسافات والشرطات
    cleaned = re.sub(r"[\s\-\(\)]+", "", value.strip())

    # إزالة البادئة 00 وتحويلها إلى +
    if cleaned.startswith("00967"):
        cleaned = "+" + cleaned[2:]

    # إذا يبدأ بـ 967 بدون + → إضافة +
    if cleaned.startswith("967") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned

    # إذا يبدأ بـ 7 (رقم محلي 9 أرقام) → إضافة +967
    if re.match(r"^7\d{8}$", cleaned):
        cleaned = PHONE_COUNTRY_CODE + cleaned

    if cleaned == original.strip():
        return value, None

    return cleaned, {
        "rule_code": "PHONE_NORMALIZE",
        "original_value": original,
        "corrected_value": cleaned,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║         القاعدة 6: تصحيح البريد الإلكتروني (EMAIL_FIX)      ║
# ╚══════════════════════════════════════════════════════════════╝

def rule_email_fix(value):
    """
    تصحيح تكرار الرموز الشائعة في البريد الإلكتروني:
    - @@ → @
    - .. → . (في الجزء بعد @)
    - إزالة المسافات الزائدة
    
    مثال: "user@@example..com" → "user@example.com"
    """
    if not value or not isinstance(value, str):
        return value, None

    original = value
    cleaned = value.strip()

    # تصحيح @@ → @
    while "@@" in cleaned:
        cleaned = cleaned.replace("@@", "@")

    # تصحيح .. → . (في النطاق فقط)
    if "@" in cleaned:
        local_part, domain = cleaned.rsplit("@", 1)
        while ".." in domain:
            domain = domain.replace("..", ".")
        cleaned = f"{local_part}@{domain}"

    # إزالة المسافات داخل البريد
    cleaned = cleaned.replace(" ", "")

    if cleaned == original.strip():
        return value, None

    return cleaned, {
        "rule_code": "EMAIL_FIX",
        "original_value": original,
        "corrected_value": cleaned,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║        القاعدة 7: توحيد التواريخ (DATE_NORMALIZE)           ║
# ╚══════════════════════════════════════════════════════════════╝

# صيغ التاريخ المدعومة (مرتبة حسب الأولوية)
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",       # ISO: 2025-02-24T21:29:00
    "%Y-%m-%d %H:%M:%S",       # 2025-02-24 21:29:00
    "%Y-%m-%dT%H:%M",          # 2025-02-24T21:29
    "%Y-%m-%d",                # 2025-02-24
    "%d-%m-%Y %H:%M:%S",       # DD-MM-YYYY HH:MM:SS
    "%d-%m-%Y",                # DD-MM-YYYY
    "%d/%m/%Y %H:%M:%S",       # DD/MM/YYYY HH:MM:SS
    "%d/%m/%Y",                # DD/MM/YYYY
    "%m/%d/%Y %H:%M:%S",       # MM/DD/YYYY HH:MM:SS
    "%m/%d/%Y",                # MM/DD/YYYY
]


def rule_date_normalize(value):
    """
    توحيد صيغ التواريخ إلى ISO Format (YYYY-MM-DDTHH:MM:SS).
    يدعم صيغ متعددة بما فيها DD-MM-YYYY.
    
    مثال: "17-01-2025 04:50:00" → "2025-01-17T04:50:00"
    """
    if not value or not isinstance(value, str):
        return value, None

    stripped = value.strip()

    # تحويل الأرقام العربية في التاريخ إذا وُجدت
    stripped = stripped.translate(_ARABIC_DIGIT_MAP)

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(stripped, fmt)
            iso_str = dt.strftime("%Y-%m-%dT%H:%M:%S")

            # التحقق من صلاحية التاريخ (مثلاً شهر 13 مستحيل)
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

    # لم يتطابق مع أي صيغة — سيُفحص في check_post_cleaning_quarantine
    return value, None


# ╔══════════════════════════════════════════════════════════════╗
# ║     القاعدة 8: تنظيف النصوص وتوحيد الحالات (TEXT_NORMALIZE)║
# ╚══════════════════════════════════════════════════════════════╝

# القيم المعتمدة لحالة الطلب (status)
_VALID_STATUSES = {
    "مؤكد",
    "ملغي",
    "مرتجع",
    "قيد الانتظار",
    "قيد الشحن",
    "تم التسليم",
    "قيد الشحن",
}


def rule_text_normalize(value, field_name="status"):
    """
    إزالة المسافات الزائدة (Trim) وتوحيد حالة الطلب.
    
    مثال: "  قيد الشحن  " → "قيد الشحن"
    """
    if not value or not isinstance(value, str):
        return value, None

    original = value

    # إزالة المسافات الزائدة من الأطراف وبين الكلمات
    cleaned = " ".join(value.split())

    if cleaned == original:
        return value, None

    return cleaned, {
        "rule_code": "TEXT_NORMALIZE",
        "original_value": original,
        "corrected_value": cleaned,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║     القاعدة 9: إعادة حساب الإجمالي (TOTAL_RECALC)          ║
# ╚══════════════════════════════════════════════════════════════╝

def rule_total_recalc(record, items):
    """
    إعادة حساب إجمالي الطلب ومطابقته مع مجموع العناصر والتوصيل.
    total_amount = sum(item.total for each item) + delivery_cost

    Parameters
    ----------
    record : dict
        السجل بعد تنظيف الحقول الرقمية.
    items : list
        قائمة العناصر بعد التنظيف.

    Returns
    -------
    tuple (corrected_total_str, audit_entry | None)
    """
    try:
        delivery_cost = float(record.get("delivery_cost", 0))
        items_total = sum(float(item.get("total", 0)) for item in items)
        expected_total = items_total + delivery_cost

        current_total_str = record.get("total_amount", "0")
        current_total = float(current_total_str)

        # مطابقة مع هامش خطأ بسيط (لتفادي مشاكل الفاصلة العائمة)
        if abs(current_total - expected_total) > 0.01:
            corrected = str(expected_total)
            return corrected, {
                "rule_code": "TOTAL_RECALC",
                "original_value": current_total_str,
                "corrected_value": corrected,
            }

        return current_total_str, None

    except (ValueError, TypeError):
        # إذا فشل الحساب — يتركها كما هي (ستُكتشف في post-cleaning)
        return record.get("total_amount", "0"), None


# ╔══════════════════════════════════════════════════════════════╗
# ║           المنسّق: تطبيق جميع القواعد التسع                 ║
# ╚══════════════════════════════════════════════════════════════╝

def _apply_numeric_rules(value, field_name, corrections):
    """تطبيق القواعد الرقمية (1-4) على حقل واحد."""
    # القاعدة 1: الأرقام العربية
    value, audit = rule_arabic_numerals(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    # القاعدة 2: نصوص العملة في المبالغ
    value, audit = rule_currency_normalize_amount(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    # القاعدة 3: فواصل الآلاف
    value, audit = rule_thousands_separator(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    # القاعدة 4: أسعار بالكلمات
    value, audit = rule_word_to_number(value)
    if audit:
        audit["field"] = field_name
        corrections.append(audit)

    return value


def apply_all_rules(record):
    """
    تطبيق جميع قواعد التنظيف التسع على سجل واحد.

    Parameters
    ----------
    record : dict
        السجل الخام (نسخة — لا يُعدّل الأصل).

    Returns
    -------
    tuple (cleaned_record, cleaned_items, corrections)
        cleaned_record : dict  — السجل بعد التنظيف
        cleaned_items  : list  — العناصر بعد التنظيف
        corrections    : list  — قائمة التصحيحات (Audit Trail)
    """
    record = dict(record)  # نسخة لتجنب تعديل الأصل
    corrections = []

    # ══════════ الحقول الرقمية: القواعد 1-4 ══════════
    for field in ("delivery_cost", "payment_amount", "total_amount"):
        val = record.get(field, "") or ""
        cleaned = _apply_numeric_rules(val, field, corrections)
        record[field] = cleaned

    # ══════════ العملة: القاعدة 2 ══════════
    currency_val = record.get("currency", "") or ""
    cleaned_currency, audit = rule_currency_normalize_field(currency_val)
    if audit:
        audit["field"] = "currency"
        corrections.append(audit)
    record["currency"] = cleaned_currency

    # ══════════ الهاتف: القاعدة 5 ══════════
    phone_val = record.get("customer_phone", "") or ""
    cleaned_phone, audit = rule_phone_normalize(phone_val)
    if audit:
        audit["field"] = "customer_phone"
        corrections.append(audit)
    record["customer_phone"] = cleaned_phone

    # ══════════ البريد: القاعدة 6 ══════════
    email_val = record.get("customer_email", "") or ""
    cleaned_email, audit = rule_email_fix(email_val)
    if audit:
        audit["field"] = "customer_email"
        corrections.append(audit)
    record["customer_email"] = cleaned_email

    # ══════════ التاريخ: القاعدة 7 ══════════
    date_val = record.get("order_date", "") or ""
    cleaned_date, audit = rule_date_normalize(date_val)
    if audit:
        audit["field"] = "order_date"
        corrections.append(audit)
    record["order_date"] = cleaned_date

    # ══════════ حالة الطلب والنصوص: القاعدة 8 ══════════
    for field in ("status", "customer_name", "city", "district",
                  "delivery_type", "payment_method", "payment_status"):
        val = record.get(field, "") or ""
        cleaned_text, audit = rule_text_normalize(val, field)
        if audit:
            audit["field"] = field
            corrections.append(audit)
        record[field] = cleaned_text

    # ══════════ معالجة عناصر الطلب (items_json) ══════════
    items_json_str = record.get("items_json", "") or ""
    items = json.loads(items_json_str)  # مُفحص مسبقاً في check_fatal_quarantine

    for idx, item in enumerate(items):
        # تنظيف الحقول الرقمية داخل كل عنصر
        for item_field in ("unit_price", "total", "qty"):
            raw_val = item.get(item_field)
            if raw_val is None:
                continue
            str_val = str(raw_val)
            cleaned = _apply_numeric_rules(str_val, f"items[{idx}].{item_field}", corrections)
            # تحويل إلى رقم بعد التنظيف
            try:
                item[item_field] = float(cleaned) if "." in cleaned else int(cleaned)
            except (ValueError, TypeError):
                item[item_field] = cleaned  # يبقى نصاً — سيُكتشف في post-cleaning

    # ══════════ القاعدة 9: إعادة حساب الإجمالي ══════════
    corrected_total, audit = rule_total_recalc(record, items)
    if audit:
        audit["field"] = "total_amount"
        corrections.append(audit)
    record["total_amount"] = corrected_total

    # ══════════ تحديث items_json بالقيم المنظفة ══════════
    record["items_json"] = json.dumps(items, ensure_ascii=False)

    return record, items, corrections
