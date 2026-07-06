from pathlib import Path
import re

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# Удаляем второе определение CREATE TABLE predictions (в методе create_tables)
# Оно начинается с "CREATE TABLE IF NOT EXISTS predictions (" после строки "async def create_tables"
pattern = r'(    async def create_tables\(self\):.*?"""\n)(        await self\.conn\.execute\("""\n            CREATE TABLE IF NOT EXISTS predictions \(.*?\)\n        """\))'

match = re.search(pattern, content, flags=re.DOTALL)
if match:
    # Заменяем дублирующий CREATE TABLE на pass
    content = content[:match.start(2)] + '        pass  # Таблица predictions уже создана выше' + content[match.end(2):]
    db_file.write_text(content, encoding="utf-8")
    print("✅ Дублирующийся CREATE TABLE predictions удалён из create_tables()!")
else:
    print("ℹ️ Дубликат не найден или уже удалён.")
