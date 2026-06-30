"""
Умное подключение всех роутеров из telegram_bot/
Автоматически находит все объекты Router и включает их в диспетчер
"""
import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Удаляем старые блоки подключения роутеров (если есть)
content = re.sub(
    r'# === АВТОМАТИЧЕСКОЕ ПОДКЛЮЧЕНИЕ ВСЕХ РОУТЕРОВ ===.*?# =================================================\n\n',
    '',
    content,
    flags=re.DOTALL
)

# Новый умный блок подключения роутеров
router_block = '''
    # === АВТОМАТИЧЕСКОЕ ПОДКЛЮЧЕНИЕ ВСЕХ РОУТЕРОВ ===
    import importlib
    import inspect
    from aiogram import Router
    
    # Список модулей для сканирования
    modules_to_scan = [
        "telegram_bot.handlers",
        "telegram_bot.favorites",
        "telegram_bot.admin_handlers",
        "telegram_bot.referral_handlers",
        "telegram_bot.vip_manager",
    ]
    
    connected_routers = []
    for module_name in modules_to_scan:
        try:
            module = importlib.import_module(module_name)
            # Ищем все объекты Router в модуле
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, Router):
                    dp.include_router(attr)
                    connected_routers.append(f"{module_name}.{attr_name}")
        except Exception as e:
            logger.debug(f"Не удалось загрузить {module_name}: {e}")
    
    if connected_routers:
        logger.info(f"✅ Подключено {len(connected_routers)} роутеров: {', '.join(connected_routers)}")
    else:
        logger.warning("⚠️ Не найдено ни одного роутера для подключения")
    # =================================================

'''

# Ищем место перед await dp.start_polling
polling_pattern = r'(\s*logger\.info\("🚀 Запускаю Telegram-поллинг\.\.\."\)\n\s*await dp\.start_polling)'

if re.search(polling_pattern, content):
    content = re.sub(polling_pattern, router_block + r'\1', content)
    path.write_text(content, encoding="utf-8")
    print("✅ Блок умного подключения роутеров успешно добавлен!")
    print("   Скрипт автоматически найдет и подключит все Router из telegram_bot/")
else:
    # Запасной вариант
    simple_pattern = r'(\s*await dp\.start_polling)'
    if re.search(simple_pattern, content):
        content = re.sub(simple_pattern, router_block + r'\1', content)
        path.write_text(content, encoding="utf-8")
        print("✅ Блок подключен (запасной вариант)!")
    else:
        print("❌ Не удалось найти await dp.start_polling в main.py")
