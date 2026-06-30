import os
from pathlib import Path

db_path = Path("database/db.py")
if db_path.exists():
    content = db_path.read_text(encoding="utf-8")
    
    target = "self.conn = await aiosqlite.connect(self.db_path)"
    
    if target in content and "os.makedirs" not in content:
        patch = """import os
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)"""
        
        content = content.replace(target, patch)
        db_path.write_text(content, encoding="utf-8")
        print("✅ Ошибка БД исправлена! Папка для базы данных теперь создается автоматически.")
    elif "os.makedirs" in content:
        print("ℹ️ Файл database/db.py уже содержит фикс.")
    else:
        print("⚠️ Не удалось найти точную строку подключения в database/db.py")
else:
    print("❌ Файл database/db.py не найден!")
