import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# 1. Исправляем автоинкремент (SQLite -> PostgreSQL)
content = re.sub(r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT', 'SERIAL PRIMARY KEY', content, flags=re.IGNORECASE)
content = re.sub(r'\bAUTOINCREMENT\b', '', content, flags=re.IGNORECASE)

# 2. Исправляем типы данных
content = re.sub(r'\bDATETIME\b', 'TIMESTAMP', content, flags=re.IGNORECASE)
content = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', content, flags=re.IGNORECASE)

db_file.write_text(content, encoding="utf-8")
print("✅ Синтаксис CREATE TABLE успешно адаптирован для PostgreSQL!")
