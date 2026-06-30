"""
Добавляет команду /run для ручного запуска pipeline (только для админа)
"""
import re
from pathlib import Path

main_path = Path("main.py")
content = main_path.read_text(encoding="utf-8")

# Проверяем, есть ли уже команда
if '@dp.message(Command("run"))' in content or '@router.message(Command("run"))' in content:
    print("ℹ️ Команда /run уже есть в коде")
    exit(0)

# Ищем место после определения диспетчера (dp или router)
# Обычно это после строки типа: dp = Dispatcher() или router = Router()

# Вариант 1: Ищем после Dispatcher()
pattern1 = r'(dp\s*=\s*Dispatcher\(\).*?\n)'
match1 = re.search(pattern1, content, re.DOTALL)

# Вариант 2: Ищем после Router()
pattern2 = r'(router\s*=\s*Router\(\).*?\n)'
match2 = re.search(pattern2, content, re.DOTALL)

# Код команды /run
run_command_code = '''

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

# Если нашли Dispatcher
if match1:
    insert_pos = match1.end()
    new_content = content[:insert_pos] + run_command_code + content[insert_pos:]
    main_path.write_text(new_content, encoding="utf-8")
    print("✅ Команда /run добавлена после Dispatcher()")
    
# Если нашли Router
elif match2:
    # Для Router нужно использовать router вместо dp
    run_command_code_router = run_command_code.replace('@dp.message', '@router.message')
    insert_pos = match2.end()
    new_content = content[:insert_pos] + run_command_code_router + content[insert_pos:]
    main_path.write_text(new_content, encoding="utf-8")
    print("✅ Команда /run добавлена после Router()")
    
else:
    print("⚠️ Не удалось найти место для вставки автоматически")
    print("💡 Добавьте команду вручную перед строкой 'if __name__ == \"__main__\":'")
    print("\nКод для вставки:")
    print(run_command_code)
