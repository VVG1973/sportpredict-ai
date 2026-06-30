import re
from pathlib import Path

main_path = Path("main.py")
if not main_path.exists():
    print("❌ main.py не найден")
    exit()

content = main_path.read_text(encoding="utf-8")
changed = False

# 1. Добавляем импорт
import_str = "from data_collectors.api_football_parser import APIFootballParser"
if import_str not in content:
    match = re.search(r'^(from data_collectors\..*)$', content, re.MULTILINE)
    if match:
        content = content.replace(match.group(1), match.group(1) + "\n" + import_str)
        changed = True
        print("✅ 1. Импорт APIFootballParser добавлен")

# 2. Внедрение в run_pipeline (с защитой от ошибок)
if "APIFootballParser()" not in content:
    pattern = r'(real_matches\s*=\s*await\s*real_sports_parser\.get_matches\(\))'
    if re.search(pattern, content):
        injection = r'''\1
        
        # 🌍 Добавляем реальные матчи летних лиг из API-Football
        try:
            api_football_parser = APIFootballParser()
            api_matches = api_football_parser.get_matches_for_dates(days_ahead=3)
            if api_matches:
                real_matches.extend(api_matches)
                logger.info(f"🌍 Добавлено {len(api_matches)} реальных летних матчей из API-Football")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка загрузки API-Football: {e}")'''
        content = re.sub(pattern, injection, content)
        changed = True
        print("✅ 2. Вызов API-Football внедрен в run_pipeline")

if changed:
    main_path.write_text(content, encoding="utf-8")
    print("💾 main.py успешно обновлен!")
else:
    print("ℹ️ Изменения не потребовались (паттерн не найден или уже добавлено)")
