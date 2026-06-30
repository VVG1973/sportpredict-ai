import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

if "_test_run" in content:
    print("ℹ️ Тестовый запуск уже есть в коде.")
else:
    # Ищем строку запуска поллинга (например, await dp.start_polling)
    match = re.search(r'^(\s*)(await\s+\w+\.start_polling.*)$', content, re.MULTILINE)
    if match:
        indent = match.group(1)
        original_line = match.group(2)
        
        injection = f"""{indent}# === ВРЕМЕННЫЙ ТЕСТОВЫЙ ЗАПУСК ===
{indent}async def _test_run():
{indent}    await asyncio.sleep(40)
{indent}    logger.info("🚀 Тестовый запуск run_pipeline...")
{indent}    try:
{indent}        await run_pipeline()
{indent}        logger.info("✅ Тестовый запуск завершен! Проверьте каналы.")
{indent}    except Exception as e:
{indent}        logger.error(f"❌ Ошибка тестового запуска: {{e}}")
{indent}asyncio.create_task(_test_run())
{indent}# ================================\n"""
        
        new_content = content[:match.start()] + injection + original_line + content[match.end():]
        path.write_text(new_content, encoding="utf-8")
        print("✅ Тестовый запуск успешно добавлен ВНУТРЬ функции main()!")
        print("💾 main.py сохранен.")
    else:
        print("⚠️ Не удалось найти start_polling. Пришлите мне скриншот конца файла main.py.")
