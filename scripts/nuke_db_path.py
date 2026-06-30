import re
from pathlib import Path

db_file = Path("database/db.py")
if not db_file.exists():
    print("❌ Файл database/db.py не найден!")
    exit(1)

content = db_file.read_text(encoding="utf-8")

# 1. Добавляем умную функцию поиска безопасного пути
helper = """
import os
from pathlib import Path

def _get_safe_db_path():
    # Вариант 1: Официальный Volume Railway (самый надежный)
    vol = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if vol and os.path.exists(vol):
        p = Path(vol) / "bot.db"
        return str(p)
    
    # Вариант 2: Локальная папка data (если есть права)
    p = Path("data")
    try:
        p.mkdir(parents=True, exist_ok=True)
        return str(p / "bot.db")
    except Exception:
        pass
        
    # Вариант 3: Системная папка /tmp (100% работает везде)
    return "/tmp/bot.db"
"""

if "_get_safe_db_path" not in content:
    content = helper + "\n" + content

# 2. Принудительно заменяем ЛЮБОЕ присвоение self.db_path на нашу функцию
content = re.sub(r'self\.db_path\s*=\s*[^\n]+', 'self.db_path = _get_safe_db_path()', content)

# 3. Добавляем создание папки прямо перед подключением (на всякий случай)
content = re.sub(
    r'(\s*)(self\.conn\s*=\s*await\s*aiosqlite\.connect\(self\.db_path\))',
    r'\1os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)\n\1\2',
    content
)

db_file.write_text(content, encoding="utf-8")
print("✅ ЯДЕРНЫЙ ФИКС ПРИМЕНЕН!")
print("📁 БД будет принудительно создана в безопасном месте (Volume или /tmp).")
