# 📊 تقرير مشروع خط البيانات الهجين (midterm-data-pipeline)

## 📌 ملخص القياسات الرسمية (قسم 6.12)
- **معرّف التشغيل (id_run)**: `run_2026-08-29T20:06:37`
- **المحمّل المستخدم (engine_used)**: `spark_loader`
- **اسم وحجم الملف المصدر (file_name / file_size_mb)**: `part_250MB.csv` (`250.0 MB`)
- **الزمن الكلي (elapsed_seconds)**: `194.28 ثانية`
- **معدل المعالجة (Throughput)**: `3,072.15 سجل/ثانية`

---

## 🧮 معادلة الاتساق والتحقق (Consistency Verification)
> **المعادلة الإلزامية (قسم 6.11)**: $\text{run\_raw\_count} = \text{run\_valid\_count} + \text{run\_corrected\_count} + \text{run\_quarantine\_count}$

| المقياس القياسي (Metric) | عدد السجلات | النسبة المئوية |
|---|---|---|
| **إجمالي السجلات الخام (raw_loaded)** | `596,857` | 100% |
| **السجلات السليمة (count_valid)** | `27,450,311` | `4599.14%` |
| **السجلات المصححة (count_corrected)** | `0` | `0.0%` |
| **السجلات المعزولة (count_quarantine)** | `2,130,403` | `356.94%` |

- **نتيجة الاتساق (Consistency Check)**: `❌ غير محققة (False)`
- **صيغة المطابقة**: `596857 = 27450311 + 0 + 2130403`

---

## ⚡ تفاصيل الـ Upsert في MongoDB (Idempotency Verification)
- **عدد السجلات الجديدة المضافة (inserted_count)**: `27,450,311`
- **عدد السجلات المعدلة مع أثر التصحيح (updated_count)**: `0`
- **الفهرس الفريد المعتمد (Unique Index)**: `order_id` في كولكشن `orders_validated`

---

## 💻 تخصيص الموارد المتقدم (Dynamic Resource Allocation)
- **أنوية المعالج (cores_allocated)**: `7` مخصصة من إجمالي `8` (تم حجز 1 للنظام).
- **الذاكرة (RAM)**: `3.9 GB` (نسبة 80% من المتاحة `4.9 GB`).
- **حجم الدفعة (batch_size)**: `50,000` سجل.

---

## 🛠️ تفاصيل أخطاء العزل (error_case_counts)
| رمز كود الخطأ (Error Code) | عدد السجلات المعزولة |
|---|---|
| `ID_ORDER_MISSING` | `4,165` |
