"""
═══════════════════════════════════════════════════════════════════
المحمّل التراكمي — Path B / Distinction (src/incremental_loader.py)
───────────────────────────────────────────────────────────────────
خاصية التمييز (Path B / distinction):
يسمح بتحميل دفعة جديدة تراكمية (Incremental Batch) من الطلبات دون تكرار
السجلات القائمة، معتمدة على الـ Unique Index والـ Upsert في MongoDB.
═══════════════════════════════════════════════════════════════════
"""

import logging
from src.mongo_setup import bulk_upsert_validated, bulk_upsert_quarantine

logger = logging.getLogger(__name__)


def process_incremental_batch(records_validated, records_quarantine):
    """
    معالجة وتحميل دفعة إضافية (Incremental Batch) إلى MongoDB
    دون المساس بالسجلات المعتمدة سابقاً، مع حفظخاصية الـ Idempotency.

    Parameters
    ----------
    records_validated : list
        قائمة السجلات السليمة/المصححة المراد تحديثها/إضافتها.
    records_quarantine : list
        قائمة السجلات التالفة المراد تحديثها/إضافتها.
    """
    logger.info(
        "Incremental Loader (Path B): بدء معالجة الدفعة التراكمية (Validated=%d | Quarantine=%d)",
        len(records_validated), len(records_quarantine)
    )

    if records_validated:
        bulk_upsert_validated(records_validated)
        logger.info("تم تحديث/إضافة %d سجل تراكمي إلى orders_validated بنجاح.", len(records_validated))

    if records_quarantine:
        bulk_upsert_quarantine(records_quarantine)
        logger.info("تم تحديث/إضافة %d سجل تراكمي إلى orders_quarantine بنجاح.", len(records_quarantine))

    return len(records_validated), len(records_quarantine)
