import re
from pathlib import Path

parsers_dir = Path("data_collectors")

# Массив всех топ-лиг для API-Football
ALL_LEAGUES = """
ALL_LEAGUES = [
    39,   # Premier League (England)
    140,  # La Liga (Spain)
    135,  # Serie A (Italy)
    78,   # Bundesliga (Germany)
    61,   # Ligue 1 (France)
    88,   # Eredivisie (Netherlands)
    94,   # Primeira Liga (Portugal)
    235,  # Super Lig (Turkey)
    71,   # Serie A (Brazil)
    7,    # MLS (USA)
    1,    # FIFA World Cup
    2,    # UEFA Champions League
    3,    # UEFA Europa League
]
"""

# Массив для TheSportsDB (по названиям)
ALL_COMPETITIONS = """
ALL_COMPETITIONS = [
    "English Premier League",
    "Spanish La Liga",
    "Italian Serie A",
    "German Bundesliga",
    "French Ligue 1",
    "Dutch Eredivisie",
    "Portuguese Primeira Liga",
    "Turkish Super Lig",
    "Brazilian Serie A",
    "American Major League Soccer",
    "FIFA World Cup",
    "UEFA Champions League",
    "UEFA Europa League",
]
"""

changed_files = []

for file in parsers_dir.glob("*.py"):
    content = file.read_text(encoding="utf-8")
    original = content
    
    # 1. Добавляем массив ALL_LEAGUES в начало файла (если его нет)
    if "ALL_LEAGUES" not in content and "league_id" in content:
        # Вставляем после импортов
        import_section_end = content.find('\n\n', content.find('import '))
        if import_section_end != -1:
            content = content[:import_section_end] + ALL_LEAGUES + content[import_section_end:]
            changed_files.append(file.name)
    
    # 2. Добавляем массив ALL_COMPETITIONS для TheSportsDB
    if "ALL_COMPETITIONS" not in content and "COMPETITIONS" in content:
        import_section_end = content.find('\n\n', content.find('import '))
        if import_section_end != -1:
            content = content[:import_section_end] + ALL_COMPETITIONS + content[import_section_end:]
            if file.name not in changed_files:
                changed_files.append(file.name)
    
    # 3. Заменяем league_id=39 на цикл по всем лигам
    if "league_id: int = 39" in content or "league_id=39" in content:
        # Для функций с параметром league_id
        content = re.sub(
            r'league_id:\s*int\s*=\s*39',
            'league_id: int = None  # Will iterate over ALL_LEAGUES',
            content
        )
        
        # Находим функцию fetch_upcoming_matches и добавляем цикл
        if "async def fetch_upcoming_matches" in content and "for league_id in ALL_LEAGUES" not in content:
            # Ищем тело функции и добавляем цикл
            pattern = r'(async def fetch_upcoming_matches.*?:\s*\n)((?:\s+.*\n)*)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                func_def = match.group(1)
                func_body = match.group(2)
                
                # Добавляем цикл в начало функции
                loop_code = """        all_matches = []
        leagues_to_check = ALL_LEAGUES if league_id is None else [league_id]
        for league_id in leagues_to_check:
"""
                # Увеличиваем отступы в существующем коде
                indented_body = '\n'.join('    ' + line if line.strip() else line for line in func_body.split('\n'))
                
                # Добавляем сохранение результатов
                save_results = """
            all_matches.extend(matches)
        return all_matches
"""
                new_func = func_def + loop_code + indented_body + save_results
                content = content[:match.start()] + new_func + content[match.end():]
                if file.name not in changed_files:
                    changed_files.append(file.name)
    
    # 4. Для TheSportsDB - заменяем жестко прописанные лиги на ALL_COMPETITIONS
    if "COMPETITIONS = [" in content and "ALL_COMPETITIONS" in content:
        content = re.sub(
            r'COMPETITIONS\s*=\s*\[[^\]]*\]',
            'COMPETITIONS = ALL_COMPETITIONS',
            content
        )
        if file.name not in changed_files:
            changed_files.append(file.name)
    
    if content != original:
        file.write_text(content, encoding="utf-8")

if changed_files:
    print(f"✅ Все топ-лиги добавлены в парсеры: {', '.join(changed_files)}")
    print("🌍 Теперь бот будет собирать матчи из 13 лиг мира!")
else:
    print("ℹ️ Изменения не потребовались.")
