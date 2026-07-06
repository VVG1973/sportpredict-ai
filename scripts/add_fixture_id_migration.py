from pathlib import Path
import re

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# Ищем место после CREATE TABLE predictions и добавляем ALTER TABLE
alter_code = '''        # Миграция: добавляем fixture_id если его нет
        try:
            await self.conn.execute("""
                ALTER TABLE predictions 
                ADD COLUMN IF NOT EXISTS fixture_id TEXT
            """)
        except Exception:
            pass
'''

# Вставляем после "✅ Таблицы PostgreSQL созданы/проверены"
if "ADD COLUMN IF NOT EXISTS fixture_id" not in content:
    content = content.replace(
        'print("✅ Таблицы PostgreSQL созданы/проверены")',
        'print("✅ Таблицы PostgreSQL созданы/проверены")\n' + alter_code
    )
    db_file.write_text(content, encoding="utf-8")
    print("✅ Миграция для fixture_id добавлена в database/db.py!")
else:
    print("ℹ️ Миграция уже существует.")
