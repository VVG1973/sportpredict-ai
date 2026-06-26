"""
Интеграция реальных xG данных из Understat
Объединяет агрегированную статистику команд с коэффициентами букмекеров
Создаёт ЧЕСТНЫЕ pre-match признаки
"""
import csv
import json
import logging
from pathlib import Path
from typing import Dict, List
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def similarity(a: str, b: str) -> float:
    """Вычисляет сходство двух строк"""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_best_match(team_name: str, available_teams: List[str]) -> str:
    """Находит наиболее похожее название команды"""
    best_match = None
    best_score = 0
    
    for available in available_teams:
        score = similarity(team_name, available)
        if score > best_score:
            best_score = score
            best_match = available
    
    return best_match if best_score > 0.7 else None


def parse_understat_csv(file_path: Path) -> Dict[str, Dict]:
    """Парсит CSV файл с Understat и возвращает словарь {team_name: stats}"""
    teams_stats = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Understat использует ; как разделитель и " для кавычек
            reader = csv.DictReader(f, delimiter=';')
            
            for row in reader:
                team = row.get('team', '').strip('"').strip()
                if not team:
                    continue
                
                try:
                    stats = {
                        'xG': float(row.get('xG', '0').strip('"')),
                        'NPxG': float(row.get('NPxG', '0').strip('"')),
                        'xGA': float(row.get('xGA', '0').strip('"')),
                        'NPxGA': float(row.get('NPxGA', '0').strip('"')),
                        'xPTS': float(row.get('xPTS', '0').strip('"')),
                        'ppda': float(row.get('ppda', '0').strip('"')),
                        'ppda_allowed': float(row.get('ppda_allowed', '0').strip('"')),
                        'deep': float(row.get('deep', '0').strip('"')),
                        'deep_allowed': float(row.get('deep_allowed', '0').strip('"')),
                        'matches': int(row.get('matches', '0').strip('"')),
                    }
                    
                    # Вычисляем средние значения за матч
                    matches = stats['matches']
                    if matches > 0:
                        stats['xG_per_match'] = stats['xG'] / matches
                        stats['xGA_per_match'] = stats['xGA'] / matches
                        stats['NPxG_per_match'] = stats['NPxG'] / matches
                    else:
                        stats['xG_per_match'] = 0
                        stats['xGA_per_match'] = 0
                        stats['NPxG_per_match'] = 0
                    
                    teams_stats[team] = stats
                except (ValueError, TypeError) as e:
                    logger.debug(f"Пропуск команды {team}: {e}")
                    continue
        
        logger.info(f"✅ {file_path.name}: загружено {len(teams_stats)} команд")
        return teams_stats
    
    except Exception as e:
        logger.error(f"❌ Ошибка чтения {file_path}: {e}")
        return {}


def collect_understat_data(understat_dir: Path) -> Dict[str, Dict[str, Dict]]:
    """Собирает данные из всех CSV файлов Understat"""
    # Структура: {league: {season: {team: stats}}}
    all_data = {}
    
    csv_files = list(understat_dir.glob("*.csv"))
    logger.info(f"📂 Найдено {len(csv_files)} CSV файлов в {understat_dir}")
    
    for csv_file in csv_files:
        # Извлекаем лигу и сезон из имени файла
        # Формат: EPL_2024.csv, La_liga_2023.csv, Bundesliga_2022.csv
        parts = csv_file.stem.split("_")
        if len(parts) >= 2:
            league = parts[0]
            season = parts[1]  # год начала сезона (2024 = сезон 2024/2025)
            
            if league not in all_data:
                all_data[league] = {}
            
            teams_stats = parse_understat_csv(csv_file)
            if teams_stats:
                all_data[league][season] = teams_stats
    
    return all_data


def merge_with_odds(understat_data: Dict, matches: List[Dict]) -> List[Dict]:
    """Объединяет xG данные с коэффициентами букмекеров"""
    logger.info(f"🔧 Объединение данных...")
    
    # Собираем все уникальные названия команд из Understat
    all_understat_teams = []
    for league_data in understat_data.values():
        for season_data in league_data.values():
            all_understat_teams.extend(season_data.keys())
    
    all_understat_teams = list(set(all_understat_teams))
    logger.info(f"📊 Уникальных команд в Understat: {len(all_understat_teams)}")
    
    # Сопоставление лиг между football-data и Understat
    league_mapping = {
        "E0": "EPL",
        "E1": "EPL",  # Championship тоже сопоставим
        "SP1": "La_liga",
        "D1": "Bundesliga",
        "I1": "Serie_A",
        "F1": "Ligue_1",
        "N1": "EPL",  #近似
        "P1": "La_liga",  #近似
        "B1": "Bundesliga",  #近似
        "T1": "Bundesliga",  #近似
    }
    
    merged = []
    matched_count = 0
    
    for match in matches:
        fd_league = match.get("league", "")
        season = match.get("season", 0)
        home_team = match.get("home_team", "")
        away_team = match.get("away_team", "")
        
        # Преобразуем лигу
        us_league = league_mapping.get(fd_league)
        if not us_league or us_league not in understat_data:
            merged.append(match)
            continue
        
        # Для pre-match признаков берём данные ПРОШЛОГО сезона
        prev_season = str(season - 1)
        
        if prev_season not in understat_data[us_league]:
            merged.append(match)
            continue
        
        season_data = understat_data[us_league][prev_season]
        
        # Ищем команды
        home_match = find_best_match(home_team, list(season_data.keys()))
        away_match = find_best_match(away_team, list(season_data.keys()))
        
        if home_match and away_match:
            home_stats = season_data[home_match]
            away_stats = season_data[away_match]
            
            # Добавляем ЧЕСТНЫЕ pre-match признаки
            match["home_season_xG"] = home_stats['xG_per_match']
            match["away_season_xG"] = away_stats['xG_per_match']
            match["home_season_xGA"] = home_stats['xGA_per_match']
            match["away_season_xGA"] = away_stats['xGA_per_match']
            
            # Разница в силе атаки/защиты
            match["xG_attack_diff"] = home_stats['xG_per_match'] - away_stats['xG_per_match']
            match["xG_defense_diff"] = home_stats['xGA_per_match'] - away_stats['xGA_per_match']
            
            # Атака хозяев vs защита гостей
            match["home_attack_vs_away_defense"] = home_stats['xG_per_match'] - away_stats['xGA_per_match']
            # Атака гостей vs защита хозяев
            match["away_attack_vs_home_defense"] = away_stats['xG_per_match'] - home_stats['xGA_per_match']
            
            # NPxG (без пенальти)
            match["home_season_NPxG"] = home_stats['NPxG_per_match']
            match["away_season_NPxG"] = away_stats['NPxG_per_match']
            
            # PPDA (индекс прессинга)
            match["home_ppda"] = home_stats['ppda']
            match["away_ppda"] = away_stats['ppda']
            
            # xPTS (ожидаемые очки)
            match["home_xPTS"] = home_stats['xPTS']
            match["away_xPTS"] = away_stats['xPTS']
            
            matched_count += 1
        
        merged.append(match)
    
    logger.info(f"✅ Сопоставлено {matched_count} из {len(matches)} матчей")
    return merged


def main():
    print("=" * 60)
    print("🔧 ИНТЕГРАЦИЯ РЕАЛЬНЫХ XG ИЗ UNDERSTAT")
    print("=" * 60)
    print()
    
    # 1. Собираем xG данные из Understat
    understat_dir = Path("data/historical/understat")
    if not understat_dir.exists():
        print(f"❌ Папка не найдена: {understat_dir}")
        print("💡 Создайте папку и положите туда CSV файлы")
        return
    
    understat_data = collect_understat_data(understat_dir)
    
    if not understat_data:
        print("❌ Не удалось загрузить данные из Understat")
        return
    
    # Статистика
    print("\n📊 СТАТИСТИКА ПО ЛИГАМ:")
    for league, seasons in understat_data.items():
        print(f"  {league}: {len(seasons)} сезонов")
        for season, teams in seasons.items():
            print(f"    {season}: {len(teams)} команд")
    
    # 2. Загружаем данные матчей
    matches_path = Path("data/historical/football_data_matches_with_xg.json")
    if not matches_path.exists():
        print(f"❌ Файл не найден: {matches_path}")
        return
    
    with open(matches_path, "r", encoding="utf-8") as f:
        matches = json.load(f)
    
    print(f"\n📚 Загружено {len(matches)} матчей")
    
    # 3. Объединяем
    merged = merge_with_odds(understat_data, matches)
    
    # 4. Сохраняем
    output_path = Path("data/historical/football_data_matches_real_xg.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Сохранено {len(merged)} матчей с реальными xG")
    print(f"   JSON: {output_path}")
    
    # Проверяем последний матч
    if merged:
        last = merged[-1]
        print(f"\n📊 Последний матч: {last.get('date')} - {last.get('home_team')} vs {last.get('away_team')}")
        print(f"   home_season_xG: {last.get('home_season_xG', 'N/A')}")
        print(f"   away_season_xG: {last.get('away_season_xG', 'N/A')}")
        print(f"   xG_attack_diff: {last.get('xG_attack_diff', 'N/A')}")
    
    print("\n✅ Готово к переобучению модели!")


if __name__ == "__main__":
    main()
