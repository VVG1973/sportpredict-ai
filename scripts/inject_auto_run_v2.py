"""
Добавляет автозапуск run_pipeline через 30 секунд после старта бота
"""
import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

if "_auto_run_test" not in content:
    # Код для автозапуска
    auto_run_code = '''

# === АВТОМАТИЧЕСКИЙ ТЕСТОВЫЙ ЗАПУСК PIPELINE ===
async def _auto_run_test():
    """Запускает run_pipeline через 30 секунд для тестирования"""
    await asyncio.sleep(30)
    logger.info("🚀 Автоматический тестовый запуск run_pipeline...")
    try:
        await run_pipeline()
        logger.info("✅ Тестовый запуск успешно завершен! Проверьте каналы.")
    except Exception as e:
        logger.error(f"❌ Ошибка при тестовом запуске: {e}")

# Запускаем фоновую задачу
asyncio.create_task(_auto_run_test())
# ================================================

'''
    
    # Вставляем код перед if __name__ == "__main__":
    if 'if __name__ == "__main__":' in content:
        content = content.replace('if __name__ == "__main__":', auto_run_code + 'if __name__ == "__main__":')
        path.write_text(content, encoding="utf-8")
        print("✅ Автозапуск run_pipeline добавлен! (через 30 секунд после старта)")
    else:
        # Если нет if __name__, добавляем в конец
        content += auto_run_code
        path.write_text(content, encoding="utf-8")
        print("✅ Автозапуск run_pipeline добавлен в конец файла!")
else:
    print("ℹ️ Автозапуск уже добавлен в main.py.")
