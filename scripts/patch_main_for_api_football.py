"""
Патч main.py: добавляем API-Football как источник реальных матчей
"""
import re
from pathlib import Path

main_path = Path("main.py")
if not main_path.exists():
    print(f"❌ Файл не найден: {main_path}")
    exit(1)

content = main_path.read_text(encoding="utf-8")

# Добавляем импорт API-Football парсера
if "from data_collectors.api_football_parser import APIFootballParser" not in content:
    # Ищем место после других импортов парсеров
    import_pattern = r'(from data_collectors\.real_sports_parser import RealSportsParser)'
    if re.search(import_pattern, content):
        content = re.sub(
            import_pattern,
            r'\1\nfrom data_collectors.api_football_parser import APIFootballParser',
            content
        )
        print("✅ Добавлен импорт APIFootballParser")

# Ищем функцию run_pipeline и добавляем вызов API-Football
if "api_football_parser = APIFootballParser()" not in content:
    # Ищем место где инициализируются парсеры
    pipeline_pattern = r'(async def run_pipeline\(\):.*?real_sports_parser = RealSportsParser\(\))'
    match = re.search(pipeline_pattern, content, re.DOTALL)
    
    if match:
        # Добавляем инициализацию API-Football
        new_code = match.group(1) + "\n    api_football_parser = APIFootballParser()"
        content = content.replace(match.group(1), new_code)
        print("✅ Добавлена инициализация APIFootballParser")

# Добавляем получение матчей из API-Football
if "api_matches = api_football_parser.get_matches_for_dates" not in content:
    # Ищем место где получаются реальные матчи
    matches_pattern = r'(real_matches = await real_sports_parser\.get_matches\(\))'
    if re.search(matches_pattern, content):
        new_code = r'''\1
        
        # Получаем матчи из API-Football (летние лиги)
        api_matches = api_football_parser.get_matches_for_dates(days_ahead=3)
        real_matches.extend(api_matches)
        
        if api_matches:
            logger.info(f"🌍 Добавлено {len(api_matches)} матчей из API-Football")
'''
        content = re.sub(matches_pattern, new_code, content)
        print("✅ Добавлен вызов API-Football в run_pipeline")

main_path.write_text(content, encoding="utf-8")
print("\n✅ main.py обновлён для использования API-Football!")
