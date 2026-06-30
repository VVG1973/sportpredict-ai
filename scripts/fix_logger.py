from pathlib import Path

db_file = Path("database/db.py")
if not db_file.exists():
    print("❌ Файл database/db.py не найден!")
    exit(1)

content = db_file.read_text(encoding="utf-8")

# Проверяем, есть ли уже определение logger
if "logger = logging.getLogger" not in content:
    # Добавляем import logging и создание logger в самое начало файла
    injection = "import logging\nlogger = logging.getLogger(__name__)\n"
    content = injection + content
    db_file.write_text(content, encoding="utf-8")
    print("✅ Успешно добавлен 'logger' в начало database/db.py!")
else:
    print("ℹ️ 'logger' уже определен в database/db.py.")
