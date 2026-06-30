"""
Интеграция APIFootballParser в run_pipeline
"""
import re
from pathlib import Path

main_path = Path("main.py")
content = main_path.read_text(encoding="utf-8")

# Проверяем, есть ли уже импорт APIFootballParser
if "from data_collectors.api_football_parser import APIFootballParser" not in content:
    # Добавляем импорт после MultiSportParser
    pattern = r'(from data_collectors\.multi_sport_parser import MultiSportParser)'
    if re.search(pattern, content):
        content = re.sub(
            pattern,
            r'\1\nfrom data_collectors.api_football_parser import APIFootballParser',
            content
        )
        print("✅ Добавлен импорт APIFootballParser")

# Проверяем, есть ли уже вызов APIFootballParser в run_pipeline
if "api_football_parser = APIFootballParser()" not in content:
    # Ищем место после инициализации parser = MultiSportParser(...)
    pattern = r'(parser\s*=\s*MultiSportParser\([^)]+\))'
    match = re.search(pattern, content)
    
    if match:
        insert_code = f'''{match.group(1)}
    api_football_parser = APIFootballParser()  # 🆕 API-Football для летних лиг'''
        content = content.replace(match.group(1), insert_code)
        print("✅ Добавлена инициализация APIFootballParser")

# Добавляем вызов API-Football после fetch_upcoming_matches
if "api_matches = api_football_parser.get_matches_for_dates" not in content:
    pattern = r'(matches\s*=\s*await\s*parser\.fetch_upcoming_matches\([^)]+\))'
    match = re.search(pattern, content)
    
    if match:
        insert_code = f'''{match.group(1)}
    
    # 🆕 Добавляем реальные матчи из API-Football (летние лиги)
    try:
        api_matches = api_football_parser.get_matches_for_dates(days_ahead=3)
        if api_matches:
            matches.extend(api_matches)
            logger.info(f"🌍 Добавлено {{len(api_matches)}} реальных матчей из API-Football")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка загрузки API-Football: {{e}}")'''
        content = content.replace(match.group(1), insert_code)
        print("✅ Добавлен вызов API-Football в run_pipeline")

main_path.write_text(content, encoding="utf-8")
print("\n💾 main.py сохранён!")
