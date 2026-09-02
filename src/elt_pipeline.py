"""
═══════════════════════════════════════════════════════════════════
محرك المعالجة الاستئنافي والهجين — ELT Pipeline (src/elt_pipeline.py)
───────────────────────────────────────────────────────────────────
ميزات الاستئناف والـ Idempotency والتأمين من الانقطاع المفاجئ:
  1. Idempotent Upsert: إذا انقطع البرنامج وأُعيد تشغيله، لا تتكرر السجلات في orders_validated.
  2. Incremental Resume Checkpoint: يفحص السجلات المعالجة مسبقاً ليستأنف من حيث توقف.
  3. حماية البيانات من التكرار وضمان معادلة الاتساق.
═══════════════════════════════════════════════════════════════════
"""

import os
import time
import logging
from datetime import datetime, timezone

from config.settings import DEFAULT_CSV_PATH, TRANSFORM_BATCH_SIZE
from src.resource_manager import get_optimal_resources
from src.mongo_setup import (
    setup_indexes,
    drop_raw_collection,
    reset_all_collections,
    get_raw_collection,
    get_validated_collection,
    get_quarantine_collection,
    bulk_upsert_validated,
    bulk_upsert_quarantine,
)
from src.file_router import route_file
from src.quality_rules import (
    check_fatal_quarantine,
    apply_all_rules,
    check_post_cleaning_quarantine,
    build_quarantine_doc,
    build_validated_doc,
)
from src.metrics import generate_and_save_metrics

logger = logging.getLogger(__name__)


def run_elt_pipeline(csv_path=None, reset=False, progress_callback=None, max_rows=None, enabled_rules=None, enabled_quarantines=None):
    """
    تشغيل خط المعالجة الهجين المكتمل مع دعم الاستئناف التلقائي وتحديد عدد السجلات والقواعد المخصصة.
    """
    start_time = time.time()
    csv_path = csv_path or DEFAULT_CSV_PATH

    # 1. تخصيص الموارد المحسوب
    resources = get_optimal_resources()

    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}"
    logger.info("═" * 60)
    logger.info("بدء تشغيل خط المعالجة الهجين (run_id: %s)", run_id)
    logger.info("الموارد المخصصة: %d أنوية | ذاكرة: %.1f GB | دفعة: %s",
                resources["cores_allocated"], resources["allocated_memory_gb"], f"{resources['dynamic_batch_size']:,}")
    if max_rows and max_rows > 0:
        logger.info("🔢 تم تحديد عدد السجلات المراد معالجتها: %s سجل", f"{max_rows:,}")
    logger.info("═" * 60)

    # 2. إعداد الفهارس وقاعدة البيانات
    if reset:
        logger.warning("⚠️ خيار --reset مفعّل: تصفير وحذف جميع الكولكشنات...")
        reset_all_collections()

    setup_indexes()

    raw_collection = get_raw_collection()
    validated_collection = get_validated_collection()
    quarantine_collection = get_quarantine_collection()
    existing_raw_count = raw_collection.estimated_document_count()

    # 3. مرحلة EL (تحميل السجلات الخام للملف المختار إلى orders_raw)
    logger.info("─── مرحلة EL: تحميل السجلات الخام للملف المختار إلى orders_raw ───")
    if progress_callback:
        progress_callback({
            "phase": "el_loading",
            "message": "📥 جاري قراءة الملف وتمرير البيانات الخام إلى كولكشن orders_raw في MongoDB...",
            "progress_percent": 15,
            "processed": 0,
            "total": 0,
            "remaining": 0,
        })

    # تفريغ كولكشن orders_raw فقط للملف المختار، مع الحفاظ على orders_validated و orders_quarantine لاختبار منع التكرار والاستئناف
    drop_raw_collection()
    loader_name, raw_count, file_size_mb = route_file(csv_path, resources, max_rows=max_rows)

    target_total = min(raw_count, max_rows) if (max_rows and max_rows > 0) else raw_count

    # إرسال إشعار اكتمال التحميل إلى MongoDB وأن المعالجة تبدأ الآن!
    if progress_callback:
        progress_callback({
            "phase": "el_completed",
            "message": f"✅ تم تحميل البيانات إلى مانقو ديبي بنجاح ({raw_count:,} سجل خام)! ⚡ الان تبداء المعالجة والتنظيف...",
            "progress_percent": 35,
            "total": target_total,
            "processed": 0,
            "remaining": target_total,
        })

    # 4. مرحلة T (التنظيف والتصنيف مع دعم الاستئناف الفوري)
    logger.info("─── مرحلة T: التنظيف والتصنيف وقواعد الجودة ───")
    batch_size = min(resources["dynamic_batch_size"], TRANSFORM_BATCH_SIZE)

    existing_validated_count = validated_collection.estimated_document_count() if not reset else 0
    existing_quarantine_count = quarantine_collection.estimated_document_count() if not reset else 0
    already_processed_count = existing_validated_count + existing_quarantine_count

    is_resumed = bool(already_processed_count > 0 and not reset)

    if already_processed_count > 0 and not reset:
        logger.info("🔄 استئناف ذكي: تم العثور على %s سجل معالج مسبقاً في قاعدة البيانات.", f"{already_processed_count:,}")

    valid_count = 0
    quarantine_count = 0
    corrected_count = 0

    quarantine_reasons = {}
    correction_rules = {}

    validated_batch = []
    quarantine_batch = []
    processed = 0
    skipped_count = 0
    newly_added_count = 0

    # معالجة السجلات الخام على دفعات مع فحص التكرار اللحظي فائق السرعة عبر الفهرس
    cursor = raw_collection.find({}).batch_size(batch_size)

    raw_buffer = []

    def process_raw_buffer(buf):
        nonlocal processed, skipped_count, newly_added_count, valid_count, quarantine_count, corrected_count
        nonlocal validated_batch, quarantine_batch

        if not buf:
            return

        batch_order_ids = [str(doc.get("order_id", "")).strip() for doc in buf if doc.get("order_id")]
        
        already_existing_ids = set()
        if not reset and batch_order_ids:
            try:
                v_ids = {d["order_id"] for d in validated_collection.find({"order_id": {"$in": batch_order_ids}}, {"order_id": 1, "_id": 0})}
                q_ids = {d["order_id"] for d in quarantine_collection.find({"order_id": {"$in": batch_order_ids}}, {"order_id": 1, "_id": 0})}
                already_existing_ids = v_ids.union(q_ids)
            except Exception as e:
                logger.warning("تنبيه فحص الفهرس: %s", e)

        for raw_doc in buf:
            if max_rows and max_rows > 0 and processed >= max_rows:
                break

            processed += 1

            if progress_callback and (processed % 1000 == 0 or processed == target_total):
                rem = max(0, target_total - processed)
                pct = 35 + int((processed / max(1, target_total)) * 60)
                progress_callback({
                    "phase": "t_transforming",
                    "message": f"⚙️ جاري المعالجة والتنظيف... (تم معالجة {processed:,} من أصل {target_total:,} | باقي: {rem:,} سجل)",
                    "progress_percent": pct,
                    "total": target_total,
                    "processed": processed,
                    "remaining": rem,
                })

            order_id = str(raw_doc.get("order_id", "")).strip()

            # فحص التكرار والاستئناف
            if order_id and order_id in already_existing_ids and not reset:
                skipped_count += 1
                continue

            newly_added_count += 1
            raw_record = {k: v for k, v in raw_doc.items() if k != "_id"}

            fatal_result = check_fatal_quarantine(raw_record, enabled_quarantines=enabled_quarantines)
            if fatal_result:
                error_code, _ = fatal_result
                q_doc = build_quarantine_doc(raw_record, error_code, run_id)
                quarantine_batch.append(q_doc)
                quarantine_count += 1
                quarantine_reasons[error_code] = quarantine_reasons.get(error_code, 0) + 1

                if len(quarantine_batch) >= batch_size:
                    bulk_upsert_quarantine(quarantine_batch)
                    quarantine_batch = []
                continue

            try:
                cleaned_record, cleaned_items, corrections = apply_all_rules(raw_record, enabled_rules=enabled_rules)
            except Exception as e:
                logger.warning("خطأ أثناء تنظيف %s: %s", raw_record.get("order_id", "?"), e)
                q_doc = build_quarantine_doc(raw_record, "JSON_ITEMS_CORRUPTED", run_id)
                quarantine_batch.append(q_doc)
                quarantine_count += 1
                quarantine_reasons["JSON_ITEMS_CORRUPTED"] = quarantine_reasons.get("JSON_ITEMS_CORRUPTED", 0) + 1

                if len(quarantine_batch) >= batch_size:
                    bulk_upsert_quarantine(quarantine_batch)
                    quarantine_batch = []
                continue

            post_result = check_post_cleaning_quarantine(cleaned_record, enabled_quarantines=enabled_quarantines)
            if post_result:
                error_code, _ = post_result
                q_doc = build_quarantine_doc(raw_record, error_code, run_id)
                quarantine_batch.append(q_doc)
                quarantine_count += 1
                quarantine_reasons[error_code] = quarantine_reasons.get(error_code, 0) + 1

                if len(quarantine_batch) >= batch_size:
                    bulk_upsert_quarantine(quarantine_batch)
                    quarantine_batch = []
                continue

            v_doc = build_validated_doc(cleaned_record, cleaned_items, corrections, run_id)
            validated_batch.append(v_doc)

            if corrections:
                corrected_count += 1
                for c in corrections:
                    r_code = c["rule_code"]
                    correction_rules[r_code] = correction_rules.get(r_code, 0) + 1
            else:
                valid_count += 1

            if len(validated_batch) >= batch_size:
                bulk_upsert_validated(validated_batch)
                validated_batch = []

    for raw_doc in cursor:
        if max_rows and max_rows > 0 and processed >= max_rows:
            break
        raw_buffer.append(raw_doc)
        if len(raw_buffer) >= 2000:
            process_raw_buffer(raw_buffer)
            raw_buffer = []

    if raw_buffer and not (max_rows and max_rows > 0 and processed >= max_rows):
        process_raw_buffer(raw_buffer)
        raw_buffer = []

    if validated_batch:
        bulk_upsert_validated(validated_batch)
        validated_batch = []
    # حساب العدادات الحقيقية النهائية بأسرع طريقة O(1) لتجنب Full Collection Scan
    total_quarantine = quarantine_collection.estimated_document_count()
    total_validated = validated_collection.estimated_document_count()

    total_valid = valid_count if not is_resumed else max(0, total_validated - corrected_count)
    total_corrected = corrected_count

    stats = {
        "valid_count": total_valid,
        "corrected_count": total_corrected,
        "quarantine_count": total_quarantine,
        "quarantine_reasons": quarantine_reasons,
        "correction_rules": correction_rules,
        "is_resumed": is_resumed,
        "previously_processed_rows": already_processed_count,
        "new_rows_added": newly_added_count,
    }

    # 5. مرحلة R (التقارير والمقاييس)
    end_time = time.time()
    report = generate_and_save_metrics(
        run_id, loader_name, file_size_mb, raw_count, stats, resources,
        start_time, end_time, file_path=csv_path
    )

    logger.info("اكتمل تشغيل الخط وميزات الاستئناف بنجاح في %.2f ثانية", end_time - start_time)
    return report
