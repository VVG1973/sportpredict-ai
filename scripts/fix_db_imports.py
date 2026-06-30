import re
from pathlib import Path

db_file = Path("database/db.py")
if not db_file.exists():
    print("❌ Файл database/db.py не найден!")
    exit(1)

content = db_file.read_text(encoding="utf-8")

required_imports = [
    "import aiosqlite",
    "import os",
    "import logging",
    "from pathlib import Path"
]

added = []
for imp in required_imports:
    if imp not in content:
        content = imp + "\n" + content
        added.append(imp)

if added:
    db_file.write_text(content, encoding="utf-8")
    print(f"✅ Успешно добавлены недостающие импорты в database/db.py: {', '.join(added)}")
else:
    print("ℹ️ Все необходимые импорты уже на месте.")
