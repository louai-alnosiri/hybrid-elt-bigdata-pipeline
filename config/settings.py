"""
═══════════════════════════════════════════════════════════════════
الإعدادات المركزية لمشروع خط البيانات الهجين (midterm-data-pipeline)
───────────────────────────────────────────────────────────────────
جميع المتغيرات تُدار من هذا الملف حصراً.
ممنوع تشتيت الإعدادات داخل الأكواد الأخرى.
القيم قابلة للتعديل عبر متغيرات البيئة (Environment Variables).
═══════════════════════════════════════════════════════════════════
"""

import os

# ╔══════════════════════════════════════════════════════════════╗
# ║                     إعدادات الملف المصدر                    ║
# ╚══════════════════════════════════════════════════════════════╝
DEFAULT_CSV_PATH = os.getenv("CSV_FILE_PATH", os.path.join("data", "orders_huge_mixed_quality.csv") if os.path.exists(os.path.join("data", "orders_huge_mixed_quality.csv")) else "orders_huge_mixed_quality.csv")
SAMPLE_CSV_PATH = os.path.join("data", "orders_sample_small.csv")
CSV_ENCODING = "utf-8-sig"                 # الملف مشفّر بـ UTF-8 مع BOM
FILE_SIZE_THRESHOLD_MB = int(os.getenv("FILE_SIZE_THRESHOLD_MB", "200"))

# ╔══════════════════════════════════════════════════════════════╗
# ║                     إعدادات Apache Spark (المسار A)          ║
# ╚══════════════════════════════════════════════════════════════╝
# للوضع المحلي: local[*] | لعنقود مستقل (Path A): spark://MASTER_IP:7077
SPARK_MASTER_URL = os.getenv("SPARK_MASTER_URL", "local[*]")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "ecommerce_elt")
RAW_COLLECTION = "orders_raw"
VALIDATED_COLLECTION = "orders_validated"
QUARANTINE_COLLECTION = "orders_quarantine"

# ╔══════════════════════════════════════════════════════════════╗
# ║                   إعدادات المعالجة بالدفعات                 ║
# ╚══════════════════════════════════════════════════════════════╝
DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", "5000"))
TRANSFORM_BATCH_SIZE = int(os.getenv("TRANSFORM_BATCH_SIZE", "5000"))

# ╔══════════════════════════════════════════════════════════════╗
# ║                إعدادات إدارة الموارد الديناميكية             ║
# ╚══════════════════════════════════════════════════════════════╝
MEMORY_FRACTION = float(os.getenv("MEMORY_FRACTION", "0.8"))   # نسبة الذاكرة المتاحة للتخصيص (80%)
LEAVE_CORES = int(os.getenv("LEAVE_CORES", "1"))               # أنوية محجوزة لنظام التشغيل (1 Core)

# ╔══════════════════════════════════════════════════════════════╗
# ║                     إعدادات التنظيف                         ║
# ╚══════════════════════════════════════════════════════════════╝
PHONE_COUNTRY_CODE = "+967"                 # رمز اليمن الدولي
TARGET_CURRENCY = "YER"                     # العملة المعتمدة

# ╔══════════════════════════════════════════════════════════════╗
# ║                     إعدادات التقارير                        ║
# ╚══════════════════════════════════════════════════════════════╝
REPORTS_DIR = "reports"
RESULTS_JSON_FILE = os.path.join(REPORTS_DIR, "results.json")
RESULTS_MD_FILE = os.path.join(REPORTS_DIR, "results.md")

# ╔══════════════════════════════════════════════════════════════╗
# ║                    ترتيب أعمدة CSV                          ║
# ╚══════════════════════════════════════════════════════════════╝
CSV_COLUMNS = [
    "order_id",         # معرّف الطلب
    "order_date",       # تاريخ الطلب
    "status",           # حالة الطلب
    "customer_id",      # معرّف العميل
    "customer_name",    # اسم العميل
    "customer_phone",   # هاتف العميل
    "customer_email",   # بريد العميل
    "city",             # المدينة
    "district",         # الحي/المنطقة
    "delivery_type",    # نوع التوصيل
    "delivery_cost",    # تكلفة التوصيل
    "payment_method",   # طريقة الدفع
    "payment_status",   # حالة الدفع
    "payment_amount",   # مبلغ الدفع
    "currency",         # العملة
    "total_amount",     # إجمالي الطلب
    "items_json",       # عناصر الطلب (JSON)
]
