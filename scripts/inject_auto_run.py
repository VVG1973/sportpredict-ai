import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

if "_auto_run" not in content:
    if "await dp.start_polling" in content:
        lines = content.split('\n')
        target_line = ""
        for line in lines:
            if "await dp.start_polling" in line:
                target_line = line
                break
        
        if target_line:
            # Определяем отступы строки, чтобы не сломать синтаксис
            indent = target_line[:len(target_line) - len(target_line.lstrip())]
            
            injection = f"""{indent}# === АВТОМАТИЧЕСКИЙ ТЕСТОВЫЙ ЗАПУСК PIPELINE ===
{indent}async def _auto_run():
{indent}    await asyncio.sleep(20)  # Ждем 20 сек, пока бот полностью запустится
{indent}    logger.info("🚀 Автоматический тестовый запуск run_pipeline...")
{indent}    try:
{indent}        await run_pipeline()
{indent}        logger.info("✅ Тестовый запуск успешно завершен! Проверьте каналы.")
{indent}    except Exception as e:
{indent}        logger.error(f"❌ Ошибка при тестовом запуске: {{e}}")
{indent}asyncio.create_task(_auto_run())
{indent}# ================================================\n"""
            
            content = content.replace(target_line, injection + target_line)
            path.write_text(content, encoding="utf-8")
            print("✅ Успешно добавлен автозапуск run_pipeline за 20 секунд до старта бота!")
        else:
            print("⚠️ Целевая строка не найдена.")
    else:
        print("⚠️ В main.py нет 'await dp.start_polling'.")
else:
    print("ℹ️ Автозапуск уже добавлен в main.py.")
