"""
═══════════════════════════════════════════════════════════════════
اختبارات التصنيف ومعادلة الاتساق (tests/test_classification.py)
───────────────────────────────────────────────────────────────────
اختبارات آلية لتصنيف السجلات (Valid / Corrected / Quarantine)
والتحقق من معادلة الاتساق: run_raw = run_valid + run_corrected + run_quarantine
═══════════════════════════════════════════════════════════════════
"""

import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from src.quality_rules import check_fatal_quarantine, apply_all_rules


def test_quarantine_missing_id():
    rec = {"order_id": "", "customer_id": "cust-1", "order_date": "2025-01-01", "items_json": "[]"}
    res = check_fatal_quarantine(rec)
    assert res is not None
    assert res[0] == "ID_ORDER_MISSING"


def test_quarantine_corrupted_json():
    rec = {"order_id": "ord-1", "customer_id": "cust-1", "order_date": "2025-01-01", "items_json": "not-json"}
    res = check_fatal_quarantine(rec)
    assert res is not None
    assert res[0] == "JSON_ITEMS_CORRUPTED"


def test_quarantine_negative_value():
    rec = {
        "order_id": "ord-1", "customer_id": "cust-1", "order_date": "2025-01-01",
        "items_json": '[{"qty": -2, "unit_price": 100, "total": 200}]',
        "payment_amount": "100", "total_amount": "100", "delivery_cost": "0"
    }
    res = check_fatal_quarantine(rec)
    assert res is not None
    assert res[0] == "VALUE_NEGATIVE_AMBIGUOUS"


def test_classification_and_consistency():
    records = [
        # Valid
        {
            "order_id": "ord-1", "customer_id": "cust-1", "order_date": "2025-01-01T10:00:00",
            "status": "مؤكد", "customer_name": "علي", "customer_phone": "+967712345678",
            "customer_email": "user@example.com", "city": "صنعاء", "district": "التحرير",
            "delivery_type": "سريع", "delivery_cost": "2000.0", "payment_method": "نقداً",
            "payment_status": "تم الدفع", "payment_amount": "22000.0", "currency": "YER",
            "total_amount": "22000.0", "items_json": '[{"sku":"SKU1","qty":1,"unit_price":20000.0,"total":20000.0}]'
        },
        # Corrected (Arabic numeral + spaces)
        {
            "order_id": "ord-2", "customer_id": "cust-2", "order_date": "2025-01-01T10:00:00",
            "status": "  مؤكد  ", "customer_name": "محمد", "customer_phone": "712345678",
            "customer_email": "user@@example..com", "city": "عدن", "district": "كريتر",
            "delivery_type": "عادي", "delivery_cost": "٢٠٠٠٫٠", "payment_method": "بطاقة",
            "payment_status": "تم الدفع", "payment_amount": "52000.0", "currency": "ريال",
            "total_amount": "52000.0", "items_json": '[{"sku":"SKU2","qty":1,"unit_price":50000.0,"total":50000.0}]'
        },
        # Quarantine (Missing order_id)
        {
            "order_id": "", "customer_id": "cust-3", "order_date": "2025-01-01T10:00:00",
            "items_json": "[]"
        }
    ]

    raw_count = len(records)
    valid_count = 0
    corrected_count = 0
    quarantine_count = 0

    for r in records:
        fatal = check_fatal_quarantine(r)
        if fatal:
            quarantine_count += 1
            continue
        cleaned, items, corrections = apply_all_rules(r)
        if corrections:
            corrected_count += 1
        else:
            valid_count += 1

    assert raw_count == valid_count + corrected_count + quarantine_count
    print(f"✅ Consistency Equation Verified: {raw_count} = {valid_count} + {corrected_count} + {quarantine_count}")


if __name__:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    test_quarantine_missing_id()
    test_quarantine_corrupted_json()
    test_quarantine_negative_value()
    test_classification_and_consistency()
    print("✅ All classification & consistency tests passed!")
