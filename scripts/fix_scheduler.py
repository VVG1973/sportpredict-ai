"""
Добавляет misfire_grace_time и ручной запуск pipeline
"""
from pathlib import Path
import re

main_path = Path("main.py")
content = main_path.read_text(encoding="utf-8")

# 1. Добавляем misfire_grace_time к run_pipeline
pattern = r"(scheduler\.add_job\(\s*run_pipeline.*?id=['\"]run_pipeline['\"])"
match = re.search(pattern, content, re.DOTALL)

if match and "misfire_grace_time" not in match.group(1):
    old = match.group(1)
    new = old.rstrip(')') + ", misfire_grace_time=3600*12)"
    content = content.replace(old, new)
    print("✅ Добавлен misfire_grace_time к run_pipeline")
else:
    print("ℹ️ misfire_grace_time уже есть или паттерн не найден")

# 2. Добавляем команду /run для ручного запуска
if '@dp.message(Command("run"))' not in content:
    run_cmd = '''

# === РУЧНОЙ ЗАПУСК PIPELINE (для админа) ===
@dp.message(Command("run"))
async def cmd_run_pipeline(message: Message):
    """Ручной запуск pipeline (только для админа)"""
    from config import settings
    
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("⛔ Доступ запрещён")
        return
    
    await message.answer("🚀 Запуск pipeline...")
    
    try:
        await run_pipeline()
        await message.answer("✅ Pipeline завершён успешно! Проверьте каналы.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        logger.error(f"Ошибка ручного запуска: {e}")
'''
    # Вставляем перед if __name__ == "__main__":
    if 'if __name__ == "__main__":' in content:
        content = content.replace('if __name__ == "__main__":', run_cmd + '\nif __name__ == "__main__":')
        print("✅ Добавлена команда /run для ручного запуска")

main_path.write_text(content, encoding="utf-8")
print("\n💾 main.py сохранён!")
