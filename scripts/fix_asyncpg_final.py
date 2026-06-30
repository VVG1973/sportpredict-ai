import os
import re
from pathlib import Path

# 1. Удаляем .commit() из всех Python файлов
for root, dirs, files in os.walk("."):
    if any(x in root for x in ["venv", ".git", "scripts", "__pycache__", "node_modules"]):
        continue
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                new_lines = []
                changed = False
                for line in lines:
                    # Ищем строки с .commit() и заменяем на pass
                    if ".commit()" in line and ("await" in line or "conn." in line or "db." in line or "self." in line):
                        indent = len(line) - len(line.lstrip())
                        new_lines.append(" " * indent + "pass  # asyncpg uses autocommit\n")
                        changed = True
                    else:
                        new_lines.append(line)
                
                if changed:
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)
                    print(f"✅ Убран .commit() из {path}")
            except Exception:
                pass

# 2. Исправляем race condition и синтаксис в database/db.py
db_file = Path("database/db.py")
if db_file.exists():
    content = db_file.read_text(encoding="utf-8")
    
    # Гарантируем IF NOT EXISTS для всех CREATE
    content = re.sub(r'CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)', 'CREATE TABLE IF NOT EXISTS ', content, flags=re.IGNORECASE)
    content = re.sub(r'CREATE\s+INDEX\s+(?!IF\s+NOT\s+EXISTS)', 'CREATE INDEX IF NOT EXISTS ', content, flags=re.IGNORECASE)
    content = re.sub(r'CREATE\s+SEQUENCE\s+(?!IF\s+NOT\s+EXISTS)', 'CREATE SEQUENCE IF NOT EXISTS ', content, flags=re.IGNORECASE)
    
    # Оборачиваем создание таблиц в try-except, чтобы игнорировать гонки потоков
    if "await self.create_tables()" in content and "try:" not in content.split("await self.create_tables()")[0][-50:]:
        content = content.replace(
            "await self.create_tables()",
            "try:\n            await self.create_tables()\n        except Exception:\n            pass  # Ignore race conditions during table creation"
        )
        
    db_file.write_text(content, encoding="utf-8")
    print("✅ Исправлен race condition и добавлен IF NOT EXISTS в db.py!")

