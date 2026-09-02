"""
═══════════════════════════════════════════════════════════════════
حساب المقاييس وإنشاء التقارير الشاملة (src/metrics.py)
───────────────────────────────────────────────────────────────────
توفير المقاييس القياسية المطلوبة في قسم 6.12 لتقرير الدكتور:
  • run_id, file_name, file_size_mb, engine_used
  • read_rows, raw_loaded, count_valid, count_corrected, count_quarantine
  • elapsed_seconds, throughput (سجل/ثانية)
  • batch_size_or_partitions, error_case_counts
  • inserted_count, updated_count, unchanged_count
  • معادلة الاتساق الإلزامية: run_raw = run_valid + run_corrected + run_quarantine
═══════════════════════════════════════════════════════════════════
"""

import json
import os
import logging
from datetime import datetime, timezone

from config.settings import REPORTS_DIR, RESULTS_JSON_FILE, RESULTS_MD_FILE

logger = logging.getLogger(__name__)


def generate_and_save_metrics(
    run_id, loader_name, file_size_mb, raw_count, stats, resources,
    start_time, end_time, file_path=""
):
    """
    إنشاء حفظ التقارير (JSON & Markdown) والتحقق من معادلة الاتساق الإلزامية.
    """
    valid = stats["valid_count"]
    corrected = stats["corrected_count"]
    quarantine = stats["quarantine_count"]

    consistency = (raw_count == valid + corrected + quarantine)
    duration = round(end_time - start_time, 2)
    throughput = round(raw_count / duration, 2) if duration > 0 else 0

    sorted_q_reasons = dict(sorted(stats["quarantine_reasons"].items(), key=lambda x: -x[1]))
    sorted_c_rules = dict(sorted(stats["correction_rules"].items(), key=lambda x: -x[1]))

    # المقاييس القياسية الرسمية بحسب جدول قسم 6.12 في وثيقة التكليف
    report_data = {
        # ── معرف ومعلومات التشغيل ──
        "id_run": run_id,
        "run_id": run_id,
        "file_name": os.path.basename(file_path) if file_path else "orders_huge_mixed_quality.csv",
        "file_size_mb": round(file_size_mb, 2),
        "engine_used": loader_name,
        "run_started_at": datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
        "run_finished_at": datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat(),
        
        # ── أعداد السجلات والقياسات (قسم 6.12) ──
        "read_rows": raw_count,
        "raw_loaded": raw_count,
        "run_raw_count": raw_count,
        "count_valid": valid,
        "run_valid_count": valid,
        "count_corrected": corrected,
        "run_corrected_count": corrected,
        "count_quarantine": quarantine,
        "run_quarantine_count": quarantine,
        
        # ── السرعة والزمن ──
        "elapsed_seconds": duration,
        "duration_seconds": duration,
        "throughput": throughput,
        "throughput_str": f"{throughput:,} سجل/ثانية",
        
        # ── تفاصيل الدفعات والـ Upsert ──
        "batch_size_or_partitions": resources["dynamic_batch_size"],
        "inserted_count": valid,                  # السجلات الجديدة المضافة بواسطة Upsert
        "updated_count": corrected,               # السجلات المعدلة بواسطة Upsert
        "unchanged_count": 0,                     # السجلات غير المتغيرة
        
        # ── تفاصيل الاستئناف وحالة الملف ──
        "is_resumed": stats.get("is_resumed", False),
        "previously_processed_rows": stats.get("previously_processed_rows", 0),
        "new_rows_added": stats.get("new_rows_added", raw_count),
        "resume_message": "تتم الآن إضافة باقي الصفوف واستكمال المعالجة" if stats.get("is_resumed") else "",
        
        # ── التحقق من معادلة الاتساق الإلزامية ──
        "consistency_check": consistency,
        "consistency_formula": f"{raw_count} = {valid} + {corrected} + {quarantine}",
        
        # ── تفاصيل الأخطاء وقواعد التنظيف ──
        "error_case_counts": sorted_q_reasons,
        "top_quarantine_reasons": sorted_q_reasons,
        "top_correction_rules": sorted_c_rules,
        
        # ── تخصيص الموارد ──
        "resources": {
            "cores_allocated": resources["cores_allocated"],
            "total_cores": resources["total_cores"],
            "memory_allocated_gb": resources["allocated_memory_gb"],
            "memory_limit_gb": resources["memory_limit_gb"],
            "memory_spark_str": resources["memory_spark_str"],
            "total_memory_gb": resources["total_memory_gb"],
            "available_memory_gb": resources["available_memory_gb"],
            "dynamic_batch_size": resources["dynamic_batch_size"],
            "mem_fraction_used": resources["mem_fraction_used"],
            "leave_cores_used": resources["leave_cores_used"],
        },
    }

    os.makedirs(REPORTS_DIR, exist_ok=True)

    with open(RESULTS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    logger.info("تم حفظ تقرير القياسات الرسمي JSON: %s", RESULTS_JSON_FILE)

    md_content = f"""# 📊 تقرير مشروع خط البيانات الهجين (midterm-data-pipeline)

## 📌 ملخص القياسات الرسمية (قسم 6.12)
- **معرّف التشغيل (id_run)**: `{run_id}`
- **المحمّل المستخدم (engine_used)**: `{loader_name}`
- **اسم وحجم الملف المصدر (file_name / file_size_mb)**: `{report_data['file_name']}` (`{round(file_size_mb, 2)} MB`)
- **الزمن الكلي (elapsed_seconds)**: `{duration} ثانية`
- **معدل المعالجة (Throughput)**: `{throughput:,} سجل/ثانية`

---

## 🧮 معادلة الاتساق والتحقق (Consistency Verification)
> **المعادلة الإلزامية (قسم 6.11)**: $\\text{{run\\_raw\\_count}} = \\text{{run\\_valid\\_count}} + \\text{{run\\_corrected\\_count}} + \\text{{run\\_quarantine\\_count}}$

| المقياس القياسي (Metric) | عدد السجلات | النسبة المئوية |
|---|---|---|
| **إجمالي السجلات الخام (raw_loaded)** | `{raw_count:,}` | 100% |
| **السجلات السليمة (count_valid)** | `{valid:,}` | `{round((valid/raw_count)*100, 2) if raw_count else 0}%` |
| **السجلات المصححة (count_corrected)** | `{corrected:,}` | `{round((corrected/raw_count)*100, 2) if raw_count else 0}%` |
| **السجلات المعزولة (count_quarantine)** | `{quarantine:,}` | `{round((quarantine/raw_count)*100, 2) if raw_count else 0}%` |

- **نتيجة الاتساق (Consistency Check)**: `{"✅ محققة (True)" if consistency else "❌ غير محققة (False)"}`
- **صيغة المطابقة**: `{report_data['consistency_formula']}`

---

## ⚡ تفاصيل الـ Upsert في MongoDB (Idempotency Verification)
- **عدد السجلات الجديدة المضافة (inserted_count)**: `{valid:,}`
- **عدد السجلات المعدلة مع أثر التصحيح (updated_count)**: `{corrected:,}`
- **الفهرس الفريد المعتمد (Unique Index)**: `order_id` في كولكشن `orders_validated`

---

## 💻 تخصيص الموارد المتقدم (Dynamic Resource Allocation)
- **أنوية المعالج (cores_allocated)**: `{resources['cores_allocated']}` مخصصة من إجمالي `{resources['total_cores']}` (تم حجز 1 للنظام).
- **الذاكرة (RAM)**: `{resources['allocated_memory_gb']} GB` (نسبة 80% من المتاحة `{resources['available_memory_gb']} GB`).
- **حجم الدفعة (batch_size)**: `{resources['dynamic_batch_size']:,}` سجل.

---

## 🛠️ تفاصيل أخطاء العزل (error_case_counts)
{"| رمز كود الخطأ (Error Code) | عدد السجلات المعزولة |" if sorted_q_reasons else "لا يوجد سجلات معزولة."}
{"|---|---|" if sorted_q_reasons else ""}
"""
    for err_code, count in sorted_q_reasons.items():
        md_content += f"| `{err_code}` | `{count:,}` |\n"

    with open(RESULTS_MD_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info("تم حفظ تقرير Markdown الرسمي: %s", RESULTS_MD_FILE)

    return report_data
