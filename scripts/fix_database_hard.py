import re
from pathlib import Path

db_file = Path("database/db.py")
if not db_file.exists():
    print("❌ Файл database/db.py не найден!")
    exit(1)

content = db_file.read_text(encoding="utf-8")
original = content

# 1. Добавляем import os в начало файла, если его нет
if "import os" not in content:
    content = "import os\nfrom pathlib import Path\n" + content
    print("✅ Добавлен import os и pathlib")

# 2. Ищем self.db_path и делаем его абсолютным
# Патчим: self.db_path = "data/bot.db" -> self.db_path = os.path.join(os.getcwd(), "data", "bot.db")
pattern_path = r'self\.db_path\s*=\s*["\']([^"\']+)["\']'
def make_absolute(match):
    rel_path = match.group(1)
    return f'self.db_path = os.path.join(os.getcwd(), "{rel_path}")'

content = re.sub(pattern_path, make_absolute, content)
print("✅ Путь к БД сделан абсолютным")

# 3. Жестко добавляем создание директории ПЕРЕД aiosqlite.connect
# Ищем: self.conn = await aiosqlite.connect(self.db_path)
connect_pattern = r'(\s*)(self\.conn\s*=\s*await\s*aiosqlite\.connect\(self\.db_path\))'

def add_makedirs(match):
    indent = match.group(1)
    connect_line = match.group(2)
    return f"""{indent}# === СОЗДАНИЕ ПАПКИ ДЛЯ БД ===
{indent}db_dir = os.path.dirname(self.db_path)
{indent}if db_dir:
{indent}    os.makedirs(db_dir, exist_ok=True)
{indent}    logger.debug(f"📁 Папка для БД создана/проверена: {{db_dir}}")
{indent}# ============================
{indent}{connect_line}"""

content = re.sub(connect_pattern, add_makedirs, content)
print("✅ Добавлено создание папки перед подключением к БД")

if content != original:
    db_file.write_text(content, encoding="utf-8")
    print("\n💾 database/db.py успешно обновлен!")
    print("🚀 Теперь выполняйте git add и git push")
else:
    print("⚠️ Файл не был изменен (паттерны не найдены)")
