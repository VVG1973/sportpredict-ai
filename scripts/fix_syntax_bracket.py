from pathlib import Path
import re

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# Ищем и исправляем лишнюю скобку
bad_pattern = r'self\.conn\s*=\s*await\s*aiosqlite\.connect\(_db_path\)\)'
good_line = 'self.conn = await aiosqlite.connect(_db_path)'

if re.search(bad_pattern, content):
    content = re.sub(bad_pattern, good_line, content)
    db_file.write_text(content, encoding="utf-8")
    print("✅ Лишняя скобка успешно удалена! Синтаксис исправлен.")
else:
    print("ℹ️ Лишняя скобка не найдена (возможно, уже исправлено).")
