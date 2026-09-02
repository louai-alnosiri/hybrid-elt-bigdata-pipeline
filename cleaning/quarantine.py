"""
═══════════════════════════════════════════════════════════════════
أكواد العزل (Quarantine Codes) وفحوصات العزل الجوهرية
───────────────────────────────────────────────────────────────────
تعريف رموز الأخطاء الجوهرية غير القابلة للإصلاح مع أوصافها.
فحوصات المرحلة الأولى (قبل التنظيف) والمرحلة الثالثة (بعد التنظيف).
═══════════════════════════════════════════════════════════════════
"""

import json
import re
from datetime import datetime

# ╔══════════════════════════════════════════════════════════════╗
# ║                   رموز أسباب العزل                          ║
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

# ╔══════════════════════════════════════════════════════════════╗
# ║           جدول تحويل الأرقام العربية (للفحص فقط)            ║
# ╚══════════════════════════════════════════════════════════════╝

_ARABIC_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def _try_parse_numeric(value):
    """
    محاولة تحويل قيمة إلى رقم بعد تنظيف أولي.
    تُستخدم في فحوصات العزل لتحديد هل القيمة قابلة للتحليل.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # تحويل أرقام عربية
    s = s.translate(_ARABIC_DIGIT_MAP)
    # إزالة فواصل الآلاف
    s = s.replace(",", "")
    # إزالة نصوص العملة
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
    """
    محاولة تحليل حقل items_json.
    Returns: (items_list, error_code) — أحدهما None.
    """
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


def _is_date_potentially_valid(date_str):
    """
    فحص سريع: هل التاريخ يحتوي على أرقام بالحد الأدنى؟
    الفحص النهائي يتم بعد التنظيف في المرحلة الثالثة.
    """
    if not date_str or not date_str.strip():
        return False
    s = date_str.strip()
    # يجب أن يحتوي على أرقام (لاتينية أو عربية) على الأقل
    has_digits = bool(re.search(r"[\d٠-٩]", s))
    return has_digits


# ╔══════════════════════════════════════════════════════════════╗
# ║            فحوصات العزل — المرحلة الأولى (قبل التنظيف)     ║
# ╚══════════════════════════════════════════════════════════════╝

def check_fatal_quarantine(record):
    """
    فحص الأخطاء الجوهرية التي لا يمكن معها الاستمرار بالتنظيف.
    تُستدعى قبل تطبيق أي قاعدة تنظيف.

    Parameters
    ----------
    record : dict
        السجل الخام من orders_raw.

    Returns
    -------
    tuple (error_code, error_reason) أو None
        إذا أرجعت قيمة → السجل يذهب مباشرة إلى quarantine.
        إذا أرجعت None → السجل يمكن تنظيفه.
    """
    # ── 1. معرّف الطلب مفقود ──
    order_id = (record.get("order_id") or "").strip()
    if not order_id:
        return "ID_ORDER_MISSING", QUARANTINE_CODES["ID_ORDER_MISSING"]

    # ── 2. معرّف العميل مفقود ──
    customer_id = (record.get("customer_id") or "").strip()
    if not customer_id:
        return "ID_CUSTOMER_MISSING", QUARANTINE_CODES["ID_CUSTOMER_MISSING"]

    # ── 3. تاريخ بلا محتوى رقمي على الإطلاق ──
    date_str = (record.get("order_date") or "").strip()
    if not _is_date_potentially_valid(date_str):
        return "DATE_IMPOSSIBLE_INVALID", QUARANTINE_CODES["DATE_IMPOSSIBLE_INVALID"]

    # ── 4. حقل items_json تالف أو فارغ ──
    items_json_str = (record.get("items_json") or "").strip()
    items, error_code = _try_parse_json_items(items_json_str)
    if error_code:
        return error_code, QUARANTINE_CODES[error_code]

    # ── 5. فحص القيم داخل العناصر ──
    for item in items:
        qty_val = item.get("qty")
        price_val = item.get("unit_price")

        # فحص الكميات السالبة
        qty_num = _try_parse_numeric(qty_val)
        if qty_num is not None and qty_num < 0:
            return "VALUE_NEGATIVE_AMBIGUOUS", QUARANTINE_CODES["VALUE_NEGATIVE_AMBIGUOUS"]

        # فحص الأسعار السالبة
        price_num = _try_parse_numeric(price_val)
        if price_num is not None and price_num < 0:
            return "VALUE_NEGATIVE_AMBIGUOUS", QUARANTINE_CODES["VALUE_NEGATIVE_AMBIGUOUS"]

        # فحص الأسعار غير القابلة للتحليل (??? أو نص غير رقمي)
        if price_val is not None and price_num is None:
            price_str = str(price_val).strip()
            if price_str:  # ليس فارغاً لكن غير قابل للتحليل
                return "PRICE_UNKNOWN", QUARANTINE_CODES["PRICE_UNKNOWN"]

    # ── 6. فحص حقول الأسعار الرئيسية ──
    for field_name in ("payment_amount", "total_amount", "delivery_cost"):
        val = (record.get(field_name) or "").strip()
        if val:
            num = _try_parse_numeric(val)
            if num is None:
                return "PRICE_UNKNOWN", QUARANTINE_CODES["PRICE_UNKNOWN"]

    return None  # لا يوجد خطأ جوهري — يمكن المتابعة بالتنظيف


# ╔══════════════════════════════════════════════════════════════╗
# ║         فحوصات العزل — المرحلة الثالثة (بعد التنظيف)       ║
# ╚══════════════════════════════════════════════════════════════╝

def check_post_cleaning_quarantine(record):
    """
    فحص ما بعد التنظيف — هل القيم المُنظّفة صالحة فعلاً؟

    Parameters
    ----------
    record : dict
        السجل بعد تطبيق قواعد التنظيف.

    Returns
    -------
    tuple (error_code, error_reason) أو None
    """
    # ── تاريخ لا يزال غير صالح بعد كل محاولات التحويل ──
    date_str = (record.get("order_date") or "").strip()
    if date_str:
        # محاولة تحليل ISO format
        try:
            datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return "DATE_IMPOSSIBLE_INVALID", QUARANTINE_CODES["DATE_IMPOSSIBLE_INVALID"]

    # ── أسعار لا تزال غير رقمية ──
    for field_name in ("delivery_cost", "payment_amount", "total_amount"):
        val = (record.get(field_name) or "").strip()
        if val:
            try:
                float(val)
            except (ValueError, TypeError):
                return "PRICE_UNKNOWN", QUARANTINE_CODES["PRICE_UNKNOWN"]

    return None


def build_quarantine_doc(record, error_code, run_id):
    """
    بناء مستند العزل الكامل لحفظه في orders_quarantine.

    Parameters
    ----------
    record : dict
        السجل الخام الأصلي.
    error_code : str
        رمز الخطأ (مثل ID_ORDER_MISSING).
    run_id : str
        معرّف التشغيل الحالي.

    Returns
    -------
    dict
        مستند جاهز للإدراج في orders_quarantine.
    """
    # إزالة _id لتجنب تعارض المفاتيح في MongoDB
    original = {k: v for k, v in record.items() if k != "_id"}

    return {
        "order_id": (record.get("order_id") or f"__MISSING_{id(record)}__").strip(),
        "error_code": error_code,
        "error_reason": QUARANTINE_CODES.get(error_code, "خطأ غير معروف"),
        "original_record": original,
        "quarantined_at": datetime.utcnow().isoformat(),
        "run_id": run_id,
    }
