"""Tells you which installed packages Windows (or anything else) refuses to load. Run: python scripts\\check_install.py"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: F401,E402  (sets safe defaults before other imports)

print("Python", sys.version.split()[0])
bad = 0
for mod in ["sqlalchemy", "alembic", "pydantic", "numpy", "argon2", "pymupdf", "docx", "reportlab", "yaml", "requests", "sklearn", "streamlit", "chromadb", "psycopg2"]:
    try:
        importlib.import_module(mod)
        print(f"OK       {mod}")
    except Exception as exc:                      # noqa: BLE001
        bad += 1
        print(f"BLOCKED  {mod}: {str(exc)[:110]}")
print("\nAll good." if not bad else f"\n{bad} package(s) could not load. Send me this list.")
