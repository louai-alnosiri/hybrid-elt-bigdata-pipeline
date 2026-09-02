"""
═══════════════════════════════════════════════════════════════════
تطبيق النافذة المكتبية التفاعلية (gui_app.py)
───────────────────────────────────────────────────────────────────
نافذة سطح مكتب تفاعلية بـ Windows File Explorer المباشر:
  1. اضغط زر "اختيار ملف CSV من جهازك" لفتح نافذة استعراض ملفات الويندوز المباشرة.
  2. يتم فحص حجم الملف تلقائياً وتحديد التوجيه (Python Batch vs PySpark).
  3. تنفيذ المعالجة وعرض المخرجات ومعادلة الاتساق والتقارير.
═══════════════════════════════════════════════════════════════════
"""

import os
import sys
import threading
import time
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from config.settings import DEFAULT_CSV_PATH, FILE_SIZE_THRESHOLD_MB
from src.elt_pipeline import run_elt_pipeline
from src.mongo_setup import close_connection


class HybridELTApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hybrid ELT Pipeline —   واجهة استعراض الملفات المباشرة خاصة با المهندس لؤي")
        self.root.geometry("850x680")
        self.root.configure(bg="#0f172a")

        self.selected_file_path = None
        self.file_size_mb = 0.0

        self.create_widgets()

        # اختيار الملف الافتراضي إذا وجد
        default_file = os.path.join(PROJECT_DIR, DEFAULT_CSV_PATH)
        if os.path.exists(default_file):
            self.set_selected_file(default_file)

    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#1e293b", padx=20, pady=15)
        header_frame.pack(fill="x", side="top")

        title_label = tk.Label(
            header_frame,
            text="🚀 Hybrid ELT Pipeline — نظام معالجة طلبات المتجر",
            font=("Segoe UI", 16, "bold"),
            fg="#f8fafc",
            bg="#1e293b"
        )
        title_label.pack(anchor="w")

        sub_label = tk.Label(
            header_frame,
            text="استعراض ملفات جهازك واستكشاف الحجم والتوجيه التلقائي بين PySpark و Python Batch",
            font=("Segoe UI", 10),
            fg="#94a3b8",
            bg="#1e293b"
        )
        sub_label.pack(anchor="w")

        # Main Body
        main_frame = tk.Frame(self.root, bg="#0f172a", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        # 1. قسم اختيار الملف
        file_frame = tk.LabelFrame(
            main_frame, text=" 📁 اختيار الملف من حاسوبك ",
            font=("Segoe UI", 11, "bold"), fg="#38bdf8", bg="#0f172a", padx=15, pady=15
        )
        file_frame.pack(fill="x", pady=(0, 15))

        btn_browse = tk.Button(
            file_frame,
            text="📂 استعراض واختيار ملف CSV من الكمبيوتر...",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg="#7c3aed",
            activebackground="#6d28d9",
            activeforeground="#ffffff",
            padx=20,
            pady=10,
            cursor="hand2",
            command=self.browse_file
        )
        btn_browse.pack(anchor="w", pady=(0, 10))

        self.lbl_file_path = tk.Label(
            file_frame,
            text="الملف المختار: لم يتم اختيار ملف بعد",
            font=("Segoe UI", 10),
            fg="#cbd5e1",
            bg="#0f172a",
            wraplength=780,
            justify="left"
        )
        self.lbl_file_path.pack(anchor="w")

        # 2. قسم التوجيه التلقائي والموارد
        route_frame = tk.LabelFrame(
            main_frame, text=" ⚡ التوجيه التلقائي المكتشف بحسب الحجم (حد 200MB) ",
            font=("Segoe UI", 11, "bold"), fg="#38bdf8", bg="#0f172a", padx=15, pady=15
        )
        route_frame.pack(fill="x", pady=(0, 15))

        self.lbl_size = tk.Label(
            route_frame, text="حجم الملف: -", font=("Segoe UI", 11, "bold"), fg="#f1f5f9", bg="#0f172a"
        )
        self.lbl_size.pack(anchor="w")

        self.lbl_loader = tk.Label(
            route_frame, text="المحمّل التلقائي: -", font=("Segoe UI", 12, "bold"), fg="#a78bfa", bg="#0f172a"
        )
        self.lbl_loader.pack(anchor="w", pady=5)

        self.chk_reset_var = tk.BooleanVar(value=False)
        chk_reset = tk.Checkbutton(
            route_frame,
            text="تصفير وحذف الكولكشنات في MongoDB قبل التشغيل (--reset)",
            variable=self.chk_reset_var,
            font=("Segoe UI", 10),
            fg="#fca5a5",
            bg="#0f172a",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#fca5a5"
        )
        chk_reset.pack(anchor="w", pady=(5, 0))

        # 3. زر بدء التشغيل والتقدم
        self.btn_run = tk.Button(
            main_frame,
            text="🚀 بدء المعالجة التلقائية",
            font=("Segoe UI", 13, "bold"),
            fg="#ffffff",
            bg="#10b981",
            activebackground="#059669",
            activeforeground="#ffffff",
            pady=12,
            cursor="hand2",
            command=self.start_pipeline
        )
        self.btn_run.pack(fill="x", pady=(0, 15))

        # 4. سجل النتائج
        log_frame = tk.LabelFrame(
            main_frame, text=" 📊 سجل المعالجة ومخرجات التقرير ",
            font=("Segoe UI", 11, "bold"), fg="#38bdf8", bg="#0f172a", padx=10, pady=10
        )
        log_frame.pack(fill="both", expand=True)

        self.txt_log = tk.Text(
            log_frame, bg="#020617", fg="#38bdf8", font=("Consolas", 10), wrap="word"
        )
        self.txt_log.pack(fill="both", expand=True)

    def browse_file(self):
        """فتح نافذة استعراض ملفات Windows المباشرة."""
        file_path = filedialog.askopenfilename(
            title="اختر ملف الـ CSV المعالجة من جهازك",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if file_path:
            self.set_selected_file(file_path)

    def set_selected_file(self, file_path):
        self.selected_file_path = file_path
        self.lbl_file_path.config(text=f"الملف المختار: {file_path}")

        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        self.file_size_mb = size_mb

        if size_mb > 1024:
            size_str = f"{size_mb / 1024:.2f} GB ({size_mb:.2f} MB)"
        else:
            size_str = f"{size_mb:.2f} MB"

        self.lbl_size.config(text=f"حجم الملف: {size_str}")

        if size_mb > FILE_SIZE_THRESHOLD_MB:
            self.lbl_loader.config(
                text="⚡ التوجيه التلقائي: PySpark Loader (لأن حجم الملف أكبر من 200MB)",
                fg="#c4b5fd"
            )
        else:
            self.lbl_loader.config(
                text="🐍 التوجيه التلقائي: Python Batch Loader (لأن حجم الملف أصغر من 200MB)",
                fg="#93c5fd"
            )

    def log(self, text):
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def start_pipeline(self):
        if not self.selected_file_path or not os.path.exists(self.selected_file_path):
            messagebox.showerror("خطأ", "يرجى اختيار ملف CSV صالح من جهازك أولاً!")
            return

        self.btn_run.config(state="disabled", text="⏳ جاري معالجة البيانات...")
        self.txt_log.delete("1.0", tk.END)
        self.log("═══ بدء تشغيل خط البيانات الهجين ═══")
        self.log(f"الملف المصدر: {self.selected_file_path}")
        self.log(f"حجم الملف: {self.file_size_mb:.2f} MB")

        t = threading.Thread(target=self.run_thread)
        t.daemon = True
        t.start()

    def run_thread(self):
        try:
            reset = self.chk_reset_var.get()
            report = run_elt_pipeline(csv_path=self.selected_file_path, reset=reset)

            self.root.after(0, self.on_success, report)
        except Exception as e:
            self.root.after(0, self.on_error, str(e))
        finally:
            close_connection()

    def on_success(self, report):
        self.btn_run.config(state="normal", text="🚀 بدء المعالجة التلقائية")
        self.log("\n✅ اكتملت المعالجة وحفظ التقارير بنجاح!")
        self.log(f"المحمّل المستخدم: {report['loader_used']}")
        self.log(f"المدة الإجمالية: {report['duration_seconds']} ثانية")
        self.log(f"إجمالي السجلات الخام (raw): {report['run_raw_count']:,}")
        self.log(f"السجلات السليمة (valid): {report['run_valid_count']:,}")
        self.log(f"السجلات المصححة (corrected): {report['run_corrected_count']:,}")
        self.log(f"السجلات المعزولة (quarantine): {report['run_quarantine_count']:,}")
        self.log(f"معادلة الاتساق الإلزامية: {report['consistency_formula']}")
        self.log(f"نتيجة الاتساق: {report['consistency_check']}")

        messagebox.showinfo(
            "اكتمل النجاح",
            f"تمت المعالجة بنجاح!\n\nمعادلة الاتساق: {report['consistency_formula']}\nالمدة: {report['duration_seconds']} ثانية"
        )

    def on_error(self, err_msg):
        self.btn_run.config(state="normal", text="🚀 بدء المعالجة التلقائية")
        self.log(f"\n❌ حدث خطأ أثناء المعالجة: {err_msg}")
        messagebox.showerror("خطأ في المعالجة", f"حدث خطأ أثناء تنفيذ Pipeline:\n{err_msg}")


def launch_gui():
    root = tk.Tk()
    app = HybridELTApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
