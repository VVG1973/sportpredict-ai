from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# Проверяем, есть ли уже импорт
if "from pathlib import Path" not in content and "import pathlib" not in content:
    # Добавляем в самое начало файла
    content = "from pathlib import Path\n" + content
    db_file.write_text(content, encoding="utf-8")
    print("✅ Успешно добавлен 'from pathlib import Path' в начало database/db.py!")
else:
    print("ℹ️ Импорт Path уже есть в файле.")
