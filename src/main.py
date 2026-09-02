"""
═══════════════════════════════════════════════════════════════════
نقطة الدخول الرئيسية (src/main.py)
───────────────────────────────────────────────────────────────────
الاستخدام:
  python src/main.py                  # تشغيل عادي على البيانات الرئيسية
  python src/main.py --reset          # حذف كل البيانات والبدء من الصفر
  python src/main.py --sample         # تشغيل عينة صغيرة من الملف (data/orders_sample_small.csv)
  python src/main.py --csv <path>     # تشغيل على ملف مخصص
═══════════════════════════════════════════════════════════════════
"""

import argparse
import logging
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from config.settings import DEFAULT_CSV_PATH, SAMPLE_CSV_PATH
from src.elt_pipeline import run_elt_pipeline
from src.create_small_sample import create_sample
from src.mongo_setup import close_connection


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-7s │ %(name)-22s │ %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Hybrid ELT Pipeline (midterm-data-pipeline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="حذف جميع الكولكشنات (raw, validated, quarantine) قبل التشغيل",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="استخدام عينة صغيرة اختباريّة (data/orders_sample_small.csv)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="تحديد مسار ملف CSV مختلف",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="تشغيل واجهة التحكم التفاعلية على المتصفح (Web Dashboard)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="تشغيل تطبيق استعراض الملفات المباشر على ويندوز (Windows Desktop GUI)",
    )
    return parser.parse_args()


def main():
    setup_logging()
    args = parse_args()

    if args.gui:
        from gui_app import launch_gui
        launch_gui()
        return

    if args.web:
        from src.web_app import start_server
        start_server()
        return

    if args.sample:
        csv_path = os.path.join(PROJECT_DIR, SAMPLE_CSV_PATH)
        if not os.path.exists(csv_path):
            create_sample(rows_to_copy=5000)
    elif args.csv:
        csv_path = os.path.join(PROJECT_DIR, args.csv) if not os.path.isabs(args.csv) else args.csv
    else:
        csv_path = os.path.join(PROJECT_DIR, DEFAULT_CSV_PATH) if not os.path.isabs(DEFAULT_CSV_PATH) else DEFAULT_CSV_PATH

    try:
        run_elt_pipeline(csv_path=csv_path, reset=args.reset)
    finally:
        close_connection()


if __name__ == "__main__":
    main()
