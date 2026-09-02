"""
Wrapper to execute src/main.py from workspace root.
"""
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from src.main import main

if __name__ == "__main__":
    main()
