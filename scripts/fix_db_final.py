import re
from pathlib import Path

db_file = Path("database/db.py")
if not db_file.exists():
    print("❌ Файл database/db.py не найден!")
    exit(1)

content = db_file.read_text(encoding="utf-8")

# 1. Добавляем надежную функцию создания папки в начало файла
helper = """
import os

def _get_safe_db_path():
    # Принудительно создаем папку data в текущей рабочей директории
    base_dir = os.getcwd()
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "bot.db")

"""

if "_get_safe_db_path" not in content:
    content = helper + content

# 2. Заменяем ЛЮБОЙ вызов aiosqlite.connect на нашу безопасную функцию
if "aiosqlite.connect" in content:
    content = re.sub(r'aiosqlite\.connect\([^)]+\)', 'aiosqlite.connect(_get_safe_db_path())', content)
    db_file.write_text(content, encoding="utf-8")
    print("✅ database/db.py жестко пропатчен!")
    print("📁 Теперь БД будет принудительно создаваться в папке /app/data/bot.db")
else:
    print("⚠️ Не найден вызов aiosqlite.connect")
