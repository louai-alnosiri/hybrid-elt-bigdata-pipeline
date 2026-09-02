"""
═══════════════════════════════════════════════════════════════════
اختبارات قواعد التنظيف (tests/test_cleaning_rules.py)
───────────────────────────────────────────────────────────────────
اختبارات آلية تشمل القواعد التسع لقواعد جودة البيانات مع الـ Audit Trail.
═══════════════════════════════════════════════════════════════════
"""

import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from src.quality_rules import (
    rule_arabic_numerals,
    rule_currency_normalize_amount,
    rule_currency_normalize_field,
    rule_thousands_separator,
    rule_word_to_number,
    rule_phone_normalize,
    rule_email_fix,
    rule_date_normalize,
    rule_text_normalize,
    rule_total_recalc,
    apply_all_rules,
)


def test_rule_arabic_numerals():
    v, a = rule_arabic_numerals("٧٠٦٠٠٠٫٠")
    assert v == "706000.0"
    assert a["rule_code"] == "ARABIC_NUMERALS"

    v_no, a_no = rule_arabic_numerals("123.45")
    assert v_no == "123.45"
    assert a_no is None


def test_rule_currency_normalize():
    v, a = rule_currency_normalize_amount("54000.00 ريال")
    assert v == "54000.00"
    assert a["rule_code"] == "CURRENCY_NORMALIZE"

    v_f, a_f = rule_currency_normalize_field("ريال يمني")
    assert v_f == "YER"
    assert a_f["rule_code"] == "CURRENCY_NORMALIZE"


def test_rule_thousands_separator():
    v, a = rule_thousands_separator("135,000.00")
    assert v == "135000.00"
    assert a["rule_code"] == "THOUSANDS_SEPARATOR"


def test_rule_word_to_number():
    v1, a1 = rule_word_to_number("خمسة آلاف")
    assert v1 == "5000"
    assert a1["rule_code"] == "WORD_TO_NUMBER"

    v2, a2 = rule_word_to_number("ألفان")
    assert v2 == "2000"


def test_rule_phone_normalize():
    v1, a1 = rule_phone_normalize("702390941")
    assert v1 == "+967702390941"
    assert a1["rule_code"] == "PHONE_NORMALIZE"

    v2, a2 = rule_phone_normalize("+967 776678555")
    assert v2 == "+967776678555"


def test_rule_email_fix():
    v, a = rule_email_fix("user@@example..com")
    assert v == "user@example.com"
    assert a["rule_code"] == "EMAIL_FIX"


def test_rule_date_normalize():
    v, a = rule_date_normalize("17-01-2025 04:50:00")
    assert v == "2025-01-17T04:50:00"
    assert a["rule_code"] == "DATE_NORMALIZE"


def test_rule_text_normalize():
    v, a = rule_text_normalize("  قيد الشحن  ")
    assert v == "قيد الشحن"
    assert a["rule_code"] == "TEXT_NORMALIZE"


def test_rule_total_recalc():
    rec = {"delivery_cost": "2000.0", "total_amount": "999.0"}
    items = [{"total": 30000.0}, {"total": 20000.0}]
    v, a = rule_total_recalc(rec, items)
    assert v == "52000.0"
    assert a["rule_code"] == "TOTAL_RECALC"


if __name__:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    test_rule_arabic_numerals()
    test_rule_currency_normalize()
    test_rule_thousands_separator()
    test_rule_word_to_number()
    test_rule_phone_normalize()
    test_rule_email_fix()
    test_rule_date_normalize()
    test_rule_text_normalize()
    test_rule_total_recalc()
    print("✅ All 9 cleaning rules unit tests passed!")
