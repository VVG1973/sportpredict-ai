import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# Ищем строку подключения (с любыми отступами и аргументами)
pattern = r'[ \t]*self\.conn\s*=\s*await\s*aiosqlite\.connect\([^)]+\)'

new_code = """        import os as _os
        _vol = _os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        _db_path = _os.path.join(_vol, "bot.db") if _vol else "/tmp/bot.db"
        try:
            if _os.path.dirname(_db_path):
                _os.makedirs(_os.path.dirname(_db_path), exist_ok=True)
            open(_db_path, 'a').close()  # Тестовая запись
            print(f"📁 Успешно открыли для записи: {_db_path}")
        except Exception as _e:
            print(f"⚠️ Ошибка записи в {_db_path}: {_e}. Fallback в /tmp/bot.db")
            _db_path = "/tmp/bot.db"
        
        self.conn = await aiosqlite.connect(_db_path)"""

if re.search(pattern, content):
    content = re.sub(pattern, new_code, content)
    db_file.write_text(content, encoding="utf-8")
    print("✅ Успешно внедрен надежный inline-код с fallback в /tmp!")
else:
    print("⚠️ Не удалось найти строку с aiosqlite.connect.")
