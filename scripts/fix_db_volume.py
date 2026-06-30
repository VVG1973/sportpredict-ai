import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# Удаляем старую функцию _get_safe_db_path если она есть
content = re.sub(
    r'def _get_safe_db_path\(\):.*?(?=\n(?:def |class |# |\Z))',
    '',
    content,
    flags=re.DOTALL
)

# Добавляем новую функцию в начало файла
new_function = '''import os

def _get_safe_db_path():
    """Возвращает безопасный путь к базе данных"""
    # Приоритет 1: Railway Volume
    volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if volume_path:
        db_path = os.path.join(volume_path, "bot.db")
        print(f"📁 Используем Railway Volume: {db_path}")
        return db_path
    
    # Приоритет 2: Переменная окружения DATABASE_PATH
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        print(f"📁 Используем DATABASE_PATH: {env_path}")
        return env_path
    
    # Приоритет 3: Папка data в корне проекта
    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "bot.db")
    print(f"📁 Используем локальную папку: {db_path}")
    return db_path

'''

# Вставляем функцию после импортов
if 'import os' not in content:
    content = new_function + content
else:
    # Вставляем после последнего import
    lines = content.split('\n')
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import_idx = i
    
    lines.insert(last_import_idx + 1, new_function)
    content = '\n'.join(lines)

db_file.write_text(content, encoding="utf-8")
print("✅ database/db.py обновлен с поддержкой Railway Volume")
