"""
═══════════════════════════════════════════════════════════════════
موجّه الملفات (src/file_router.py) — نقطة الدخول الوحيدة
───────────────────────────────────────────────────────────────────
يفحص حجم الملف ويوجّه المعالجة تلقائياً:
  • حجم <= الحد (200MB افتراضياً)  → Python Batch Loader
  • حجم > الحد                     → PySpark Loader
═══════════════════════════════════════════════════════════════════
"""

import os
import logging

from config.settings import FILE_SIZE_THRESHOLD_MB

logger = logging.getLogger(__name__)


def get_file_size_mb(file_path):
    """حساب حجم الملف بالميغابايت."""
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)


def route_file(file_path, resources, max_rows=None):
    """
    توجيه الملف إلى المحمّل المناسب بناءً على حجمه مع دعم تحديد عدد السجلات.
    """
    size_mb = get_file_size_mb(file_path)

    logger.info("═" * 60)
    logger.info("حجم الملف: %.2f MB | الحد المسموح: %d MB %s", size_mb, FILE_SIZE_THRESHOLD_MB, f"| الحد المطلوب: {max_rows:,} سجل" if max_rows else "")

    if size_mb <= FILE_SIZE_THRESHOLD_MB:
        logger.info("التوجيه → Python Batch Loader (مسار الملفات الصغيرة)")
        from src.batch_loader import load_csv_to_raw
        loader_name = "batch_loader"
    else:
        logger.info("التوجيه → PySpark Loader (مسار الملفات الكبيرة)")
        from src.spark_loader import load_csv_to_raw
        loader_name = "spark_loader"

    logger.info("═" * 60)

    loaded_count = load_csv_to_raw(file_path, resources, max_rows=max_rows)
    logger.info("تم تحميل %s سجل إلى orders_raw عبر %s", f"{loaded_count:,}", loader_name)

    return loader_name, loaded_count, size_mb
