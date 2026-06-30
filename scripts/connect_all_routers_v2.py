"""
Подключает ВСЕ роутеры из telegram_bot/ в правильном порядке
"""
import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Удаляем старый блок подключения роутеров
content = re.sub(
    r'# === АВТОМАТИЧЕСКОЕ ПОДКЛЮЧЕНИЕ ВСЕХ РОУТЕРОВ ===.*?# =================================================\n\n',
    '',
    content,
    flags=re.DOTALL
)

# Новый блок с явным подключением всех роутеров
router_block = '''
    # === ПОДКЛЮЧЕНИЕ ВСЕХ РОУТЕРОВ TELEGRAM-БОТА ===
    import importlib
    from aiogram import Router
    
    # Список всех модулей и их роутеров (в порядке приоритета)
    routers_config = [
        ("telegram_bot.handlers", "router"),                    # Основные команды
        ("telegram_bot.favorites", "router"),                   # Избранные команды
        ("telegram_bot.admin_handlers", "admin_router"),        # Админ-команды
        ("telegram_bot.referral_handlers", "router"),           # Реферальная система
    ]
    
    connected_routers = []
    for module_name, router_name in routers_config:
        try:
            module = importlib.import_module(module_name)
            router = getattr(module, router_name, None)
            if router and isinstance(router, Router):
                dp.include_router(router)
                connected_routers.append(f"{module_name}.{router_name}")
                logger.info(f"✅ Роутер {module_name}.{router_name} подключён")
            else:
                logger.warning(f"⚠️ Роутер {router_name} не найден в {module_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки {module_name}: {e}")
    
    if connected_routers:
        logger.info(f"✅ Всего подключено {len(connected_routers)} роутеров")
    else:
        logger.error("❌ Не подключено ни одного роутера!")
    # =================================================

'''

# Ищем место перед await dp.start_polling
polling_pattern = r'(\s*logger\.info\("🚀 Запускаю Telegram-поллинг\.\.\."\)\n\s*await dp\.start_polling)'

if re.search(polling_pattern, content):
    content = re.sub(polling_pattern, router_block + r'\1', content)
    path.write_text(content, encoding="utf-8")
    print("✅ Блок подключения всех роутеров успешно обновлён!")
    print("   Теперь будут подключены ВСЕ 4 роутера:")
    print("   - telegram_bot.handlers.router")
    print("   - telegram_bot.favorites.router")
    print("   - telegram_bot.admin_handlers.admin_router")
    print("   - telegram_bot.referral_handlers.router")
else:
    # Запасной вариант
    simple_pattern = r'(\s*await dp\.start_polling)'
    if re.search(simple_pattern, content):
        content = re.sub(simple_pattern, router_block + r'\1', content)
        path.write_text(content, encoding="utf-8")
        print("✅ Блок подключен (запасной вариант)!")
    else:
        print("❌ Не удалось найти await dp.start_polling в main.py")
