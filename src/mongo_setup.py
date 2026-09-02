"""
═══════════════════════════════════════════════════════════════════
إدارة الاتصال وقواعد بيانات MongoDB (src/mongo_setup.py)
───────────────────────────────────────────────────────────────────
  • إنشاء Unique Index على order_id في orders_validated و orders_quarantine (Idempotency)
  • عمليات Bulk Upsert عبر bulk_write (ممنوع insert عادي للسجلات التجارية)
  • إدارة دورة حياة الاتصال والتصفير
═══════════════════════════════════════════════════════════════════
"""

import logging
import pymongo
from pymongo import UpdateOne

from config.settings import (
    MONGO_URI, MONGO_DB,
    RAW_COLLECTION, VALIDATED_COLLECTION, QUARANTINE_COLLECTION,
)

logger = logging.getLogger(__name__)

_client = None


def get_client():
    """الحصول على عميل MongoDB (Singleton) مع دعم إعادة المحاولة وضبط مهلة الاتصال."""
    global _client
    if _client is None:
        _client = pymongo.MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=20000,
            connectTimeoutMS=30000,
            socketTimeoutMS=300000,
            maxIdleTimeMS=45000,
            maxPoolSize=50,
            minPoolSize=5,
            retryWrites=True,
            retryReads=True
        )
        logger.info("تم الاتصال بـ MongoDB: %s", MONGO_URI)
    return _client


def get_database():
    """الحصول على قاعدة البيانات."""
    return get_client()[MONGO_DB]


def close_connection():
    """إغلاق الاتصال بـ MongoDB."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("تم إغلاق الاتصال بـ MongoDB")


def get_raw_collection():
    """الحصول على كولكشن orders_raw."""
    return get_database()[RAW_COLLECTION]


def get_validated_collection():
    """الحصول على كولكشن orders_validated."""
    return get_database()[VALIDATED_COLLECTION]


def get_quarantine_collection():
    """الحصول على كولكشن orders_quarantine."""
    return get_database()[QUARANTINE_COLLECTION]


def setup_indexes():
    """
    إنشاء الفهارس الفريدة (Unique Index) على order_id لضمان Idempotency بدون تكرار الفحص.
    """
    try:
        val_col = get_validated_collection()
        val_indexes = val_col.index_information()
        if "idx_order_id_unique" not in val_indexes:
            val_col.create_index("order_id", unique=True, name="idx_order_id_unique", background=True)
        if "idx_quality_status" not in val_indexes:
            val_col.create_index("quality_status", name="idx_quality_status", background=True)

        quar_col = get_quarantine_collection()
        quar_indexes = quar_col.index_information()
        if "idx_quarantine_order_id_unique" not in quar_indexes:
            quar_col.create_index("order_id", unique=True, name="idx_quarantine_order_id_unique", background=True)
        logger.info("الفهارس جاهزة ومفهرسة بنجاح في قاعدة البيانات.")
    except Exception as e:
        logger.warning("تنبيه إعداد الفهارس: %s", e)


def drop_raw_collection():
    """
    حذف كولكشن orders_raw (Staging).
    تُحذف وتُعاد تعبئتها من CSV عند كل تشغيل لضمان التطابق.
    """
    get_database().drop_collection(RAW_COLLECTION)
    logger.info("تم حذف كولكشن %s (staging)", RAW_COLLECTION)


def reset_all_collections():
    """
    حذف جميع الكولكشنات الثلاث — يُستدعى مع الخيار --reset.
    """
    db = get_database()
    for col_name in [RAW_COLLECTION, VALIDATED_COLLECTION, QUARANTINE_COLLECTION]:
        db.drop_collection(col_name)
        logger.warning("تم حذف كولكشن %s (--reset)", col_name)


def bulk_insert_raw(docs):
    """إدراج دفعة من السجلات الخام إلى orders_raw بدون تنظيف."""
    if not docs:
        return 0
    collection = get_raw_collection()
    try:
        result = collection.insert_many(docs, ordered=False)
        return len(result.inserted_ids)
    except pymongo.errors.BulkWriteError as bwe:
        return bwe.details.get("nInserted", 0)


def bulk_upsert_validated(docs):
    """
    إدراج/تحديث (Upsert) للسجلات في orders_validated.
    تحقيق Idempotency يمنع التكرار عند إعادة التشغيل.
    """
    if not docs:
        return
    validated_col = get_validated_collection()
    quarantine_col = get_quarantine_collection()

    order_ids = [doc["order_id"] for doc in docs]
    quarantine_col.delete_many({"order_id": {"$in": order_ids}})

    operations = [
        UpdateOne(
            {"order_id": doc["order_id"]},
            {"$set": doc},
            upsert=True
        )
        for doc in docs
    ]
    validated_col.bulk_write(operations, ordered=False)


def bulk_upsert_quarantine(docs):
    """
    إدراج/تحديث (Upsert) للسجلات التالفة في orders_quarantine.
    """
    if not docs:
        return
    quarantine_col = get_quarantine_collection()
    validated_col = get_validated_collection()

    order_ids = [doc["order_id"] for doc in docs]
    validated_col.delete_many({"order_id": {"$in": order_ids}})

    operations = [
        UpdateOne(
            {"order_id": doc["order_id"]},
            {"$set": doc},
            upsert=True
        )
        for doc in docs
    ]
    quarantine_col.bulk_write(operations, ordered=False)
