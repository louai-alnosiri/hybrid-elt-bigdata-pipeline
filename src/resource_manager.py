"""
═══════════════════════════════════════════════════════════════════
وحدة إدارة الموارد الديناميكية (Dynamic Resource Allocation Module)
───────────────────────────────────────────────────────────────────
تفحص موارد الجهاز (CPU + RAM) في لحظة التشغيل وتخصصها بذكاء:
  • CPU: حجز نواة واحدة لنظام التشغيل، تخصيص الباقي للمعالجة.
  • RAM: تخصيص 80% من الذاكرة المتاحة، و20% حرة للنظام.
  • Batch Size: حساب ديناميكي بناءً على الذاكرة المتاحة.
═══════════════════════════════════════════════════════════════════
"""

import os
import logging

import psutil

from config.settings import MEMORY_FRACTION, LEAVE_CORES, DEFAULT_BATCH_SIZE

logger = logging.getLogger(__name__)


def get_optimal_resources(mem_fraction=None, leave_cores=None):
    """
    تحسب الموارد المثلى للتشغيل بناءً على حالة الجهاز الحالية.

    Parameters
    ----------
    mem_fraction : float, optional
        نسبة الذاكرة المتاحة للتخصيص (الافتراضي من settings.MEMORY_FRACTION).
    leave_cores : int, optional
        عدد الأنوية المحجوزة لنظام التشغيل (الافتراضي من settings.LEAVE_CORES).

    Returns
    -------
    dict
        cores_allocated      : int   — عدد الأنوية المخصصة للمعالجة
        memory_limit_gb      : float — الذاكرة المخصصة بالـ GB
        memory_spark_str     : str   — صيغة Spark (مثل "6g")
        dynamic_batch_size   : int   — حجم الدفعة الديناميكي
        total_cores          : int   — إجمالي أنوية الجهاز
        total_memory_gb      : float — إجمالي ذاكرة الجهاز
        available_memory_gb  : float — الذاكرة المتاحة حالياً
        allocated_memory_gb  : float — الذاكرة المخصصة للمعالجة
        mem_fraction_used    : float — النسبة المستخدمة
        leave_cores_used     : int   — الأنوية المحجوزة
    """
    if mem_fraction is None:
        mem_fraction = MEMORY_FRACTION
    if leave_cores is None:
        leave_cores = LEAVE_CORES

    # ═══════════════════ إدارة الأنوية (CPU) ═══════════════════
    total_cores = os.cpu_count() or 4
    cores_allocated = max(1, total_cores - leave_cores)

    logger.info(
        "CPU: إجمالي الأنوية=%d | محجوزة للنظام=%d | مخصصة للمعالجة=%d",
        total_cores, leave_cores, cores_allocated,
    )

    # ═══════════════════ إدارة الذاكرة (RAM) ═══════════════════
    mem = psutil.virtual_memory()
    available_bytes = mem.available
    total_bytes = mem.total
    allocated_bytes = int(available_bytes * mem_fraction)

    memory_limit_gb = round(allocated_bytes / (1024 ** 3), 1)
    memory_limit_gb = max(1.0, memory_limit_gb)  # 1GB كحد أدنى مطلق

    # صيغة Spark للذاكرة (عدد صحيح + g)
    memory_spark_str = f"{max(1, int(memory_limit_gb))}g"

    logger.info(
        "RAM: إجمالي=%.1fGB | متاحة=%.1fGB | مخصصة=%.1fGB (%.0f%%)",
        total_bytes / (1024 ** 3),
        available_bytes / (1024 ** 3),
        memory_limit_gb,
        mem_fraction * 100,
    )

    # ═══════════════ حجم الدفعة الديناميكي (Batch Size) ═══════════════
    batch_memory_bytes = allocated_bytes * 0.10
    estimated_row_size_bytes = 500
    dynamic_batch_size = int(batch_memory_bytes / estimated_row_size_bytes)
    dynamic_batch_size = max(1000, min(50000, dynamic_batch_size))

    logger.info(
        "Batch Size: ديناميكي=%d سجل (الافتراضي=%d)",
        dynamic_batch_size, DEFAULT_BATCH_SIZE,
    )

    return {
        "cores_allocated": cores_allocated,
        "memory_limit_gb": memory_limit_gb,
        "memory_spark_str": memory_spark_str,
        "dynamic_batch_size": dynamic_batch_size,
        "total_cores": total_cores,
        "total_memory_gb": round(total_bytes / (1024 ** 3), 1),
        "available_memory_gb": round(available_bytes / (1024 ** 3), 1),
        "allocated_memory_gb": round(allocated_bytes / (1024 ** 3), 1),
        "mem_fraction_used": mem_fraction,
        "leave_cores_used": leave_cores,
    }


def get_live_ram_stats():
    """حساب الذاكرة المستهلكة المباشرة والمتبقية للجهاز."""
    mem = psutil.virtual_memory()
    total_gb = round(mem.total / (1024 ** 3), 2)
    used_gb = round(mem.used / (1024 ** 3), 2)
    available_gb = round(mem.available / (1024 ** 3), 2)
    percent = mem.percent
    return {
        "total_gb": total_gb,
        "used_gb": used_gb,
        "available_gb": available_gb,
        "percent_used": percent,
        "ram_str": f"{used_gb} GB مستخدمة من أصل {total_gb} GB (الباقي للجهاز: {available_gb} GB)"
    }

