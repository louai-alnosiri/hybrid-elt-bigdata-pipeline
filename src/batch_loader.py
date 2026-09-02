"""
═══════════════════════════════════════════════════════════════════
محمّل بايثون بالدفعات (src/batch_loader.py)
───────────────────────────────────────────────────────────────────
للملفات الصغيرة (<= الحد المحدد مثلاً 200MB).
  ✅ يستخدم csv.DictReader مع Streaming (سطر بسطر)
  ✅ insert_many على دفعات بحجم ديناميكي
  ❌ ممنوع pandas
  ❌ ممنوع list(reader) أو قراءة الملف كاملاً في الذاكرة
  ❌ ممنوع تنظيف أو فلترة — البيانات تذهب خاماً إلى orders_raw
═══════════════════════════════════════════════════════════════════
"""

import csv
import logging

from config.settings import CSV_ENCODING
from src.mongo_setup import bulk_insert_raw

logger = logging.getLogger(__name__)


def load_csv_to_raw(file_path, resources, max_rows=None):
    """
    تحميل ملف CSV إلى orders_raw عبر Streaming بالدفعات.
    لا يقرأ الملف كاملاً في الذاكرة — يعالج سطراً بسطر مع دعم تحديد عدد السجلات.
    """
    batch_size = resources["dynamic_batch_size"]
    logger.info(
        "Python Batch Loader: بدء التحميل بحجم دفعة = %s سجل %s",
        f"{batch_size:,}",
        f"| الحد الأقصى: {max_rows:,} سجل" if max_rows else "",
    )

    total_loaded = 0
    batch = []

    with open(file_path, "r", encoding=CSV_ENCODING) as f:
        reader = csv.DictReader(f)

        for row in reader:
            batch.append(dict(row))

            if len(batch) >= batch_size:
                inserted = bulk_insert_raw(batch)
                total_loaded += inserted
                batch = []

            if max_rows and max_rows > 0 and total_loaded + len(batch) >= max_rows:
                break

        if batch:
            inserted = bulk_insert_raw(batch)
            total_loaded += inserted

    logger.info("Python Batch Loader: اكتمل التحميل — %s سجل", f"{total_loaded:,}")
    return total_loaded
