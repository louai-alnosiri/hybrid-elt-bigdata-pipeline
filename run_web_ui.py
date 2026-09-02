"""
═══════════════════════════════════════════════════════════════════
مشغل الواجهة التفاعلية المنفصل (run_web_ui.py)
───────────────────────────────────────────────────────────────────
تشغيل واجهة شبكة البيانات التفاعلية (Web Dashboard) بملف مستقل.
الاستخدام:
    python run_web_ui.py
═══════════════════════════════════════════════════════════════════
"""

import os
import sys
import webbrowser

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from src.web_app import start_server

if __name__ == "__main__":
    # فتح المتصفح تلقائياً عند التشغيل
    webbrowser.open("http://127.0.0.1:5000")
    start_server(port=5000)
