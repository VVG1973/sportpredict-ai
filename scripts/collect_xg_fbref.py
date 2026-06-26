"""
Сбор xG данных с FBref.com
FBref имеет более открытую структуру, чем Understat
"""
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Лиги на FBref (ID лиги)
LEAGUES = {
    "EPL": {"id": 9, "name": "Premier-League"},
    "La_liga": {"id": 12, "name": "La-Liga"},
    "Bundesliga": {"id": 20, "name": "Bundesliga"},
    "Serie_A": {"id": 11, "name": "Serie-A"},
    "Ligue_1": {"id": 13, "name": "Ligue-1"},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_match_table(html: str, league: str, season: int) -> List[Dict]:
    """Парсит таблицу матчей с FBref"""
    soup = BeautifulSoup(html, "lxml")
    matches = []
    
    # Ищем таблицу с результатами матчей
    # FBref использует table с классом "stats_schedule"
    tables = soup.find_all("table", {"id": lambda x: x and "schedule" in x.lower()})
    
    if not tables:
        logger.warning(f"   ⚠️ Таблица матчей не найдена для {league} {season}")
        return []
    
    for table in tables:
        rows = table.find_all("tr")
        
        for row in rows[1:]:  # Пропускаем заголовок
            try:
                cells = row.find_all(["th", "td"])
                if len(cells) < 10:
                    continue
                
                # Извлекаем данные
                date = cells[0].text.strip()
                home_team = cells[2].text.strip() if len(cells) > 2 else ""
                score = cells[3].text.strip() if len(cells) > 3 else ""
                away_team = cells[4].text.strip() if len(cells) > 4 else ""
                
                # xG данные (могут быть в разных колонках)
                home_xg = 0.0
                away_xg = 0.0
                
                for i, cell in enumerate(cells):
                    text = cell.text.strip()
                    if "xG" in text or "xg" in text:
                        try:
                            home_xg = float(cells[i+1].text.strip()) if i+1 < len(cells) else 0.0
                            away_xg = float(cells[i+2].text.strip()) if i+2 < len(cells) else 0.0
                            break
                        except (ValueError, IndexError):
                            continue
                
                if home_team and away_team and score:
                    matches.append({
                        "league": league,
                        "season": season,
                        "date": date,
                        "home_team": home_team,
                        "away_team": away_team,
                        "score": score,
                        "home_xg": home_xg,
                        "away_xg": away_xg,
                    })
            except Exception as e:
                logger.debug(f"Пропуск строки: {e}")
                continue
    
    return matches


def collect_league_season(league: str, season: int) -> List[Dict]:
    """Собирает xG данные для одной лиги за сезон"""
    league_info = LEAGUES.get(league)
    if not league_info:
        return []
    
    # FBref URL формат
    season_str = f"{season}-{season+1}"
    url = f"https://fbref.com/en/comps/{league_info['id']}/{season_str}/{season_str}-{league_info['name']}-Scores-and-Fixtures"
    
    logger.info(f"📊 Запрос: {league} {season}/{season+1}")
    
    try:
        with httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            html = response.text
            logger.info(f"   HTML получен: {len(html)} символов")
            
            matches = parse_match_table(html, league, season)
            logger.info(f"   ✅ Получено {len(matches)} матчей с xG")
            
            return matches
    
    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP ошибка {league} {season}: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Ошибка {league} {season}: {e}")
        return []


def collect_all(seasons: list = None) -> List[Dict]:
    """Собирает все лиги за указанные сезоны"""
    if seasons is None:
        current_year = datetime.now().year
        seasons = [current_year - 1, current_year - 2, current_year - 3]
    
    logger.info(f"🚀 Сбор xG данных для сезонов: {seasons}")
    logger.info(f"📊 Лиг: {len(LEAGUES)}")
    
    all_matches = []
    
    for league in LEAGUES.keys():
        for season in seasons:
            matches = collect_league_season(league, season)
            all_matches.extend(matches)
            time.sleep(3)  # FBref строгий к запросам
    
    return all_matches


def main():
    print("=" * 60)
    print("📊 СБОР XG ДАННЫХ С FBREF.COM")
    print("=" * 60)
    print()
    print("⏳ Процесс займёт 5-10 минут")
    print("🌐 Источник: fbref.com")
    print()
    
    matches = collect_all(seasons=[2024, 2023, 2022, 2021, 2020])
    
    if not matches:
        print("\n❌ Сбор данных не удался")
        print("💡 Попробуйте ручной путь (см. инструкцию ниже)")
        return
    
    # Сохраняем
    data_dir = Path("data/historical/xg")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = data_dir / "xg_matches.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Сохранено {len(matches)} матчей с xG")
    print(f"   JSON: {json_path}")
    
    # Статистика
    print("\n" + "=" * 60)
    print("📈 СТАТИСТИКА:")
    print("=" * 60)
    for league in LEAGUES.keys():
        count = sum(1 for m in matches if m["league"] == league)
        print(f"  {league:15s} : {count:4d} матчей")
    
    print(f"\n  {'ВСЕГО':15s} : {len(matches):4d} матчей")
    
    # Первые 3 матча
    print("\n" + "=" * 60)
    print("📋 ПЕРВЫЕ 3 МАТЧА:")
    print("=" * 60)
    for m in matches[:3]:
        print(f"{m['league']} | {m['home_team']} vs {m['away_team']}")
        print(f"   Счёт: {m['score']} | xG: {m['home_xg']:.2f} vs {m['away_xg']:.2f}")
        print()
    
    print("✅ Сбор завершён!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
