import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

new_func = """def _get_safe_db_path():
    import os
    import tempfile
    from pathlib import Path

    # 1. Пытаемся использовать Railway Volume
    vol = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if vol:
        try:
            os.makedirs(vol, exist_ok=True)
            test_file = Path(vol) / ".write_test"
            test_file.touch(exist_ok=True)
            test_file.unlink(missing_ok=True)
            db_path = Path(vol) / "bot.db"
            print(f"📁 Используем Railway Volume: {db_path}")
            return str(db_path)
        except Exception as e:
            print(f"⚠️ Railway Volume {vol} недоступен для записи ({e}).")

    # 2. Резервный вариант: локальная папка /app/data
    app_data = Path("/app/data")
    try:
        app_data.mkdir(parents=True, exist_ok=True)
        test_file = app_data / ".write_test"
        test_file.touch(exist_ok=True)
        test_file.unlink(missing_ok=True)
        db_path = app_data / "bot.db"
        print(f"📁 Используем локальную папку (эфемерную): {db_path}")
        return str(db_path)
    except Exception as e:
        print(f"⚠️ /app/data недоступен ({e}).")

    # 3. Крайний случай: /tmp
    db_path = Path(tempfile.gettempdir()) / "bot.db"
    print(f"📁 Используем /tmp (эфемерную): {db_path}")
    return str(db_path)
"""

start_idx = content.find("def _get_safe_db_path():")
if start_idx != -1:
    rest = content[start_idx:]
    match = re.search(r'\n(?=def |class |async def )', rest[1:])
    end_idx = start_idx + 1 + match.start() if match else len(content)
    content = content[:start_idx] + new_func + content[end_idx:]
else:
    content += "\n" + new_func

db_file.write_text(content, encoding="utf-8")
print("✅ Функция обновлена! Теперь бот сам найдет папку с правами на запись.")
