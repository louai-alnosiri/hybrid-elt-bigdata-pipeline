"""
═══════════════════════════════════════════════════════════════════
سكربت إنشاء عينة صغيرة (src/create_small_sample.py)
───────────────────────────────────────────────────────────────────
يستخرج 5,000 سجل من الملف الرئيسي الكبيرة إلى data/orders_sample_small.csv
لتجربة مسار بايثون الدفعات (batch_loader) للملفات التي حجمها <= 200MB.
═══════════════════════════════════════════════════════════════════
"""

import os
import sys
import logging

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from config.settings import DEFAULT_CSV_PATH, SAMPLE_CSV_PATH, CSV_ENCODING

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(levelname)-7s │ %(message)s")
logger = logging.getLogger(__name__)


def create_sample(rows_to_copy=5000):
    src_path = os.path.join(PROJECT_DIR, DEFAULT_CSV_PATH) if not os.path.isabs(DEFAULT_CSV_PATH) else DEFAULT_CSV_PATH
    dest_path = os.path.join(PROJECT_DIR, SAMPLE_CSV_PATH) if not os.path.isabs(SAMPLE_CSV_PATH) else SAMPLE_CSV_PATH

    if not os.path.exists(src_path):
        logger.error("الملف المصدر غير موجود: %s", src_path)
        return

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    logger.info("بدء استخراج %d سجل من %s ...", rows_to_copy, os.path.basename(src_path))

    copied = 0
    with open(src_path, "r", encoding=CSV_ENCODING) as f_in:
        with open(dest_path, "w", encoding=CSV_ENCODING, newline="") as f_out:
            for i, line in enumerate(f_in):
                f_out.write(line)
                if i > 0:
                    copied += 1
                if copied >= rows_to_copy:
                    break

    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    logger.info("تم إنشاء العينة بنجاح: %s (حجم %.2f MB | عدد السجلات %d)", dest_path, size_mb, copied)


if __name__ == "__main__":
    create_sample()
