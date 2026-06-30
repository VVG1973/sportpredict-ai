import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# 1. Добавляем колонку fixture_id через ALTER TABLE
alter_code = '''        try:
            await self.conn.execute("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS fixture_id TEXT")
        except Exception:
            pass
'''
if "ALTER TABLE predictions" not in content:
    content = content.replace(
        'print("✅ Таблицы PostgreSQL созданы/проверены")',
        alter_code + '        print("✅ Таблицы PostgreSQL созданы/проверены")'
    )

# 2. Исправляем SELECT запросы для asyncpg (execute -> fetch)
content = re.sub(
    r'cursor\s*=\s*await\s*self\.conn\.execute\((["\']SELECT.*?)\)',
    r'cursor = await self.conn.fetch(\1)',
    content,
    flags=re.IGNORECASE
)

# 3. Убираем лишний await над cursor (если он был)
content = re.sub(r'(\w+)\s*=\s*await\s+cursor', r'\1 = cursor', content)

db_file.write_text(content, encoding="utf-8")
print("✅ Исправлены SQL-запросы для asyncpg и добавлен fixture_id!")
