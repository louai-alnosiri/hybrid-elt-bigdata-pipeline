"""
═══════════════════════════════════════════════════════════════════
محمّل PySpark — المسار A المتقدم (src/spark_loader.py)
───────────────────────────────────────────────────────────────────
يدعم التشغيل في الوضع المحلي (local[*]) وعنقود Spark المستقل (Path A: Standalone Cluster)
عبر الرابط: spark://MASTER_IP:7077.
  ✅ StructType Schema ثابتة — جميع الحقول StringType (بدون inferSchema)
  ✅ foreachPartition + pymongo.insert_many بالتوازي
  ✅ قياس Throughput (سجل/ثانية) وعدد الأقسام Input Partitions
  ✅ عدم استخدام repartition عشوائي بدون تبرير
═══════════════════════════════════════════════════════════════════
"""

import os
import sys
import time
import logging

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType

from config.settings import MONGO_URI, MONGO_DB, RAW_COLLECTION, SPARK_MASTER_URL

logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════╗
# ║   Schema ثابتة — جميع الحقول String للحفاظ على القيم الخام  ║
# ╚══════════════════════════════════════════════════════════════╝
RAW_SCHEMA = StructType([
    StructField("order_id",       StringType(), True),
    StructField("order_date",     StringType(), True),
    StructField("status",         StringType(), True),
    StructField("customer_id",    StringType(), True),
    StructField("customer_name",  StringType(), True),
    StructField("customer_phone", StringType(), True),
    StructField("customer_email", StringType(), True),
    StructField("city",           StringType(), True),
    StructField("district",       StringType(), True),
    StructField("delivery_type",  StringType(), True),
    StructField("delivery_cost",  StringType(), True),
    StructField("payment_method", StringType(), True),
    StructField("payment_status", StringType(), True),
    StructField("payment_amount", StringType(), True),
    StructField("currency",       StringType(), True),
    StructField("total_amount",   StringType(), True),
    StructField("items_json",     StringType(), True),
])


def load_csv_to_raw(file_path, resources, max_rows=None):
    """
    تحميل ملف CSV إلى orders_raw عبر PySpark مع دعم تحديد عدد السجلات.
    يدعم المسار A (Spark Standalone Cluster) أو الوضع المحلي.
    """
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    cores = resources["cores_allocated"]
    mem_str = resources.get("spark_executor_memory") or resources.get("memory_spark_str", "8g")
    batch_size = resources["dynamic_batch_size"]
    master_url = SPARK_MASTER_URL

    if master_url == "local[*]":
        master_url = f"local[{cores}]"

    logger.info("═" * 60)
    logger.info("Spark Loader (المسار A): Master URL = %s", master_url)
    logger.info("إعدادات الموارد: cores=%d | memory=%s | batch=%s %s", cores, mem_str, f"{batch_size:,}", f"| limit={max_rows:,}" if max_rows else "")
    logger.info("═" * 60)

    start_time = time.time()

    spark_builder = (
        SparkSession.builder
        .appName("HybridELT_SparkLoader_PathA")
        .master(master_url)
        .config("spark.driver.memory", mem_str)
        .config("spark.executor.memory", mem_str)
        .config("spark.python.worker.connectTimeout", "300")
        .config("spark.python.worker.reuse", "true")
        .config("spark.network.timeout", "600s")
        .config("spark.sql.files.maxPartitionBytes", "67108864")  # 64MB per split
        .config("spark.ui.showConsoleProgress", "true")
    )

    spark = spark_builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    try:
        df = (
            spark.read
            .option("header", "true")
            .option("encoding", "UTF-8")
            .option("quote", '"')
            .option("escape", '"')
            .schema(RAW_SCHEMA)
            .csv(file_path)
        )

        if max_rows and max_rows > 0:
            df = df.limit(max_rows)

        num_partitions = df.rdd.getNumPartitions()
        logger.info(
            "Spark Loader (المسار A): Input Partitions = %d قسم متوازي",
            num_partitions
        )

        mongo_uri_bc = spark.sparkContext.broadcast(MONGO_URI)
        mongo_db_bc = spark.sparkContext.broadcast(MONGO_DB)
        raw_col_bc = spark.sparkContext.broadcast(RAW_COLLECTION)
        batch_size_bc = spark.sparkContext.broadcast(batch_size)

        def write_partition_to_mongo(partition):
            import pymongo

            client = pymongo.MongoClient(mongo_uri_bc.value)
            collection = client[mongo_db_bc.value][raw_col_bc.value]

            batch = []

            for row in partition:
                doc = row.asDict()
                batch.append(doc)

                if len(batch) >= batch_size_bc.value:
                    try:
                        collection.insert_many(batch, ordered=False)
                    except pymongo.errors.BulkWriteError:
                        pass
                    batch = []

            if batch:
                try:
                    collection.insert_many(batch, ordered=False)
                except pymongo.errors.BulkWriteError:
                    pass

            client.close()

        df.foreachPartition(write_partition_to_mongo)

        elapsed = time.time() - start_time
        import pymongo
        raw_client = pymongo.MongoClient(MONGO_URI)
        total_count = raw_client[MONGO_DB][RAW_COLLECTION].count_documents({})
        raw_client.close()

        throughput = round(total_count / elapsed, 2) if elapsed > 0 else 0
        logger.info("═" * 60)
        logger.info("Spark Loader (المسار A): اكتمل التحميل")
        logger.info("  إجمالي السجلات الخام المحملة : %s سجل", f"{total_count:,}")
        logger.info("  زمن التنفيذ                : %.2f ثانية", elapsed)
        logger.info("  معدل المعالجة (Throughput)  : %s سجل/ثانية", f"{throughput:,}")
        logger.info("═" * 60)

        return total_count

    finally:
        spark.stop()
        logger.info("Spark Loader: تم إيقاف SparkSession")
