import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

if "routers_to_include" in content:
    print("ℹ️ Блок подключения роутеров уже есть в main.py")
else:
    # Умный блок, который сам найдет и подключит все роутеры
    router_block = '''
    # === АВТОМАТИЧЕСКОЕ ПОДКЛЮЧЕНИЕ ВСЕХ РОУТЕРОВ ===
    import importlib
    routers_to_include = [
        ("telegram_bot.handlers", "router"),
        ("telegram_bot.handlers", "main_router"),
        ("telegram_bot.favorites", "router"),
        ("telegram_bot.favorites", "favorites_router"),
        ("telegram_bot.vip", "router"),
        ("telegram_bot.vip", "vip_router"),
        ("telegram_bot.admin", "router"),
        ("telegram_bot.admin", "admin_router"),
        ("telegram_bot.referral", "router"),
        ("telegram_bot.referral", "referral_router"),
        ("telegram_bot.stats", "router"),
        ("telegram_bot.stats", "stats_router"),
        ("telegram_bot.teams", "router"),
        ("telegram_bot.teams", "teams_router"),
    ]
    
    for module_name, router_name in routers_to_include:
        try:
            module = importlib.import_module(module_name)
            router = getattr(module, router_name)
            dp.include_router(router)
            logger.info(f"✅ Роутер {module_name}.{router_name} подключён")
        except Exception:
            pass  # Тихо пропускаем, если модуля или роутера не существует
    # =================================================

'''
    
    # Ищем место перед await dp.start_polling
    polling_pattern = r'(\s*logger\.info\("🚀 Запускаю Telegram-поллинг\.\.\."\)\n\s*await dp\.start_polling)'
    
    if re.search(polling_pattern, content):
        content = re.sub(polling_pattern, router_block + r'\1', content)
        path.write_text(content, encoding="utf-8")
        print("✅ Блок подключения роутеров успешно добавлен перед start_polling!")
    else:
        # Запасной вариант: ищем просто await dp.start_polling
        simple_pattern = r'(\s*await dp\.start_polling)'
        if re.search(simple_pattern, content):
            content = re.sub(simple_pattern, router_block + r'\1', content)
            path.write_text(content, encoding="utf-8")
            print("✅ Блок подключен (запасной вариант)!")
        else:
            print("❌ Не удалось найти await dp.start_polling в main.py")
