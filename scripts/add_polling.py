"""
Добавляет блок запуска Telegram-поллинга в конец функции main()
"""
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

if "start_polling" in content:
    print("✅ Поллинг уже есть в коде!")
else:
    # Блок кода для запуска поллинга
    polling_block = '''
    # === ЗАПУСК TELEGRAM ПОЛЛИНГА ===
    from aiogram import Bot
    from config import settings
    
    bot = Bot(token=settings.BOT_TOKEN)
    
    # Регистрируем роутеры (если они есть)
    try:
        from telegram_bot.handlers import router as bot_router
        dp.include_router(bot_router)
        logger.info("✅ Роутеры бота зарегистрированы")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось зарегистрировать роутеры: {e}")
    
    logger.info("🚀 Запускаю Telegram-поллинг...")
    await dp.start_polling(bot)
    # =================================
'''
    
    # Вставляем блок перед if __name__
    if 'if __name__ == "__main__":' in content:
        new_content = content.replace(
            'if __name__ == "__main__":',
            polling_block + '\nif __name__ == "__main__":'
        )
        path.write_text(new_content, encoding="utf-8")
        print("✅ Блок поллинга успешно добавлен!")
        print("💾 main.py сохранен")
    else:
        print("❌ Не найдена точка вставки")
