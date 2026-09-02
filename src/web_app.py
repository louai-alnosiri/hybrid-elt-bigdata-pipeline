"""
═══════════════════════════════════════════════════════════════════
لوحة التحكم التفاعلية لـ Hybrid ELT Pipeline (src/web_app.py)
───────────────────────────────────────────────────────────────────
واجهة شبكية تفاعلية مستقلة (Web Dashboard) تتيح للمستخدم:
  • رفع أو اختيار أي ملف CSV من حاسوبه أو اختيار الملفات الموجودة.
  • التوجيه والتعرف التلقائي 100% بناءً على حجم الملف (حد 200MB):
      - إذا كان الحجم <= 200MB  -> استخدام Python Batch Loader تلقائياً.
      - إذا كان الحجم > 200MB   -> استخدام PySpark Loader تلقائياً.
  • عرض التعرّف اللحظي، المدة الزمنية، تخصيص الموارد، نتائج التنظيف والرسوم البيانية.
═══════════════════════════════════════════════════════════════════
"""

import os
import sys
import threading
import logging
from glob import glob

from flask import Flask, render_template, jsonify, request

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from config.settings import DEFAULT_CSV_PATH, SAMPLE_CSV_PATH, FILE_SIZE_THRESHOLD_MB
from src.elt_pipeline import run_elt_pipeline
from src.create_small_sample import create_sample
from src.resource_manager import get_live_ram_stats

template_dir = os.path.join(PROJECT_DIR, "src", "templates")
static_dir = os.path.join(PROJECT_DIR, "src", "static")

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
logger = logging.getLogger("web_app")

pipeline_state = {
    "status": "idle",
    "phase": "idle",
    "message": "جاهز للبدء",
    "progress_percent": 0,
    "total_raw": 0,
    "processed": 0,
    "remaining": 0,
    "last_result": None,
    "error_details": None,
}


def resolve_file_path(path):
    """البحث عن الملف في المسار المباشر أو داخل مجلد data/."""
    if os.path.isabs(path) and os.path.exists(path):
        return path
    rel_path = os.path.join(PROJECT_DIR, path)
    if os.path.exists(rel_path):
        return rel_path
    data_path = os.path.join(PROJECT_DIR, "data", os.path.basename(path))
    if os.path.exists(data_path):
        return data_path
    return rel_path


def count_file_rows(full_path):
    """حساب عدد السجلات الفعلي للملفات العادية أو التقديري للملفات العملاقة."""
    try:
        size_bytes = os.path.getsize(full_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > 500:
            # ملف عملاق (مثل 12.35GB ~ 30 مليون سجل)
            approx_rows = int(size_bytes / 440)
            return approx_rows, f"~{approx_rows:,} سجل تقريباً"
        else:
            with open(full_path, 'rb') as f:
                c = sum(chunk.count(b'\n') for chunk in iter(lambda: f.read(1024*1024), b''))
                actual = max(0, c - 1)
                return actual, f"{actual:,} سجل"
    except Exception:
        return 0, "غير محدد"


def get_available_files():
    """مسح واكتشاف جميع ملفات الـ CSV المتاحة في المشروع ومجلد data."""
    files = []
    seen_paths = set()

    # مسارات الفحص الممكنة
    search_dirs = [PROJECT_DIR, os.path.join(PROJECT_DIR, "data")]
    for d in search_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".csv"):
                    full_path = os.path.join(d, f)
                    if full_path not in seen_paths and os.path.isfile(full_path):
                        size_mb = os.path.getsize(full_path) / (1024 * 1024)
                        display_name = f"الملف الرئيسي الكبير (12.6GB)" if "huge" in f or size_mb > 1000 else f"عينة صغيرة ({f})" if "sample" in f else f"ملف: {f}"
                        rows_cnt, rows_str = count_file_rows(full_path)
                        files.append({
                            "name": display_name,
                            "path": full_path,
                            "filename": f,
                            "size_mb": round(size_mb, 2),
                            "size_str": f"{size_mb / 1024:.2f} GB" if size_mb > 1024 else f"{size_mb:.2f} MB",
                            "rows_count": rows_cnt,
                            "rows_str": rows_str,
                            "recommended_loader": "spark_loader" if size_mb > FILE_SIZE_THRESHOLD_MB else "batch_loader",
                        })
                        seen_paths.add(full_path)

    # إذا لم توجد عينة صغيرة -> تنشئ واحدة فورية
    sample_path = os.path.join(PROJECT_DIR, SAMPLE_CSV_PATH)
    if not os.path.exists(sample_path):
        try:
            create_sample(rows_to_copy=5000)
            if os.path.exists(sample_path) and sample_path not in seen_paths:
                size_mb = os.path.getsize(sample_path) / (1024 * 1024)
                rows_cnt, rows_str = count_file_rows(sample_path)
                files.append({
                    "name": "عينة صغيرة تجريبية (data/orders_sample_small.csv)",
                    "path": sample_path,
                    "filename": os.path.basename(sample_path),
                    "size_mb": round(size_mb, 2),
                    "size_str": f"{size_mb:.2f} MB",
                    "rows_count": rows_cnt,
                    "rows_str": rows_str,
                    "recommended_loader": "batch_loader",
                })
        except Exception:
            pass

    return files


def on_pipeline_progress(data):
    global pipeline_state
    pipeline_state["phase"] = data.get("phase", pipeline_state["phase"])
    pipeline_state["message"] = data.get("message", pipeline_state["message"])
    pipeline_state["progress_percent"] = data.get("progress_percent", pipeline_state["progress_percent"])
    if "total" in data:
        pipeline_state["total_raw"] = data["total"]
    if "processed" in data:
        pipeline_state["processed"] = data["processed"]
    if "remaining" in data:
        pipeline_state["remaining"] = data["remaining"]


def run_pipeline_thread(target_csv_path, reset_db, max_rows=None, enabled_rules=None, enabled_quarantines=None):
    global pipeline_state
    try:
        pipeline_state["status"] = "running"
        pipeline_state["phase"] = "el_loading"
        pipeline_state["message"] = "📥 جاري فحص وتوجيه الملف وتمرير البيانات الخام إلى كولكشن orders_raw في MongoDB..."
        pipeline_state["progress_percent"] = 10
        pipeline_state["processed"] = 0
        pipeline_state["remaining"] = 0
        pipeline_state["total_raw"] = 0

        resolved_path = resolve_file_path(target_csv_path)
        report = run_elt_pipeline(
            csv_path=resolved_path,
            reset=reset_db,
            progress_callback=on_pipeline_progress,
            max_rows=max_rows,
            enabled_rules=enabled_rules,
            enabled_quarantines=enabled_quarantines,
        )

        pipeline_state["status"] = "success"
        pipeline_state["phase"] = "completed"
        pipeline_state["message"] = "🎉 اكتملت المعالجة وحفظ التقارير بنجاح!"
        pipeline_state["progress_percent"] = 100
        pipeline_state["last_result"] = report
    except Exception as e:
        logger.exception("خطأ في تشغيل Pipeline: %s", e)
        pipeline_state["status"] = "error"
        pipeline_state["phase"] = "error"
        pipeline_state["message"] = f"حدث خطأ أثناء المعالجة: {str(e)}"
        pipeline_state["error_details"] = str(e)
        pipeline_state["progress_percent"] = 0


@app.route("/")
def index():
    files = get_available_files()
    return render_template("index.html", files=files)


@app.route("/api/status")
def status():
    state = dict(pipeline_state)
    state["ram_stats"] = get_live_ram_stats()
    return jsonify(state)


@app.route("/api/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "لم يتم إرسال ملف!"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "اسم الملف فارغ!"}), 400

    save_dir = os.path.join(PROJECT_DIR, "data")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, file.filename)
    file.save(save_path)

    size_mb = os.path.getsize(save_path) / (1024 * 1024)
    rows_cnt, rows_str = count_file_rows(save_path)

    return jsonify({
        "status": "success",
        "file_path": save_path,
        "filename": file.filename,
        "size_mb": round(size_mb, 2),
        "rows_count": rows_cnt,
        "rows_str": rows_str,
        "recommended_loader": "spark_loader" if size_mb > FILE_SIZE_THRESHOLD_MB else "batch_loader"
    })


@app.route("/api/run", methods=["POST"])
def run_api():
    global pipeline_state
    if pipeline_state["status"] == "running":
        return jsonify({"status": "error", "message": "هناك عملية قيد التشغيل بالفعل!"}), 400

    data = request.get_json() or {}
    target_path = data.get("file_path") or DEFAULT_CSV_PATH
    reset_db = bool(data.get("reset", False))

    raw_max_rows = data.get("max_rows")
    max_rows = None
    if raw_max_rows:
        try:
            max_rows = int(raw_max_rows)
            if max_rows <= 0:
                max_rows = None
        except (ValueError, TypeError):
            max_rows = None

    enabled_rules = data.get("enabled_rules")
    enabled_quarantines = data.get("enabled_quarantines")

    resolved_path = resolve_file_path(target_path)
    if not os.path.exists(resolved_path):
        return jsonify({"status": "error", "message": f"الملف الموُجه غير موجود: {target_path}"}), 404

    t = threading.Thread(
        target=run_pipeline_thread,
        args=(resolved_path, reset_db, max_rows, enabled_rules, enabled_quarantines)
    )
    t.daemon = True
    t.start()

    return jsonify({"status": "started", "message": "تم بدء تشغيل Pipeline بنجاح!"})


def start_server(port=5000):
    logger.info("بدء تشغيل واجهة التحكم الشبكية التفاعلية على http://127.0.0.1:%d", port)
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    start_server()
