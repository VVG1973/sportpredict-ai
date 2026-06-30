import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# 1. Добавляем fixture_id в таблицу predictions
if "fixture_id" not in content:
    content = re.sub(
        r'(CREATE TABLE IF NOT EXISTS predictions\s*\([^)]*)\)',
        r'\1,\n                fixture_id TEXT\n            )',
        content,
        flags=re.IGNORECASE
    )
    print("✅ Добавлена колонка fixture_id")

# 2. Исправляем fetchall() для asyncpg
content = re.sub(r'\.fetchall\(\)', '', content)

db_file.write_text(content, encoding="utf-8")
print("✅ Исправлена обработка результатов для asyncpg!")
