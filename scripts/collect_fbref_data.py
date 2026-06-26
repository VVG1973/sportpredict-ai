"""
Загрузчик xG данных с FBref.com
Надёжный источник с открытым доступом
"""
import csv
import json
import logging
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# FBref лиги и их ID
LEAGUES = {
    "EPL": {"id": 9, "name": "Premier League"},
    "La_liga": {"id": 12, "name": "La Liga"},
    "Bundesliga": {"id": 20, "name": "Bundesliga"},
    "Serie_A": {"id": 11, "name": "Serie A"},
    "Ligue_1": {"id": 13, "name": "Ligue 1"},
}

LEAGUE_NAMES_RU = {
    "EPL": "Английская Премьер-лига",
    "La_liga": "Ла Лига",
    "Bundesliga": "Бундеслига",
    "Serie_A": "Серия А",
    "Ligue_1": "Лига 1",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def safe_float(value) -> float:
    try:
        return float(value) if value and value != "" else 0.0
    except (ValueError, TypeError):
        return 0.0


def safe_int(value) -> int:
    try:
        return int(value) if value and value != "" else 0
    except (ValueError, TypeError):
        return 0


def parse_fbref_match_page(html: str, league: str, season: int) -> List[Dict]:
    """Парсит страницу матча FBref"""
    soup = BeautifulSoup(html, "html.parser")
    matches = []
    
    # Ищем таблицу с результатами матчей
    # FBref использует разные селекторы для разных сезонов
    scorebox = soup.find_all("div", class_="scorebox")
    
    if not scorebox:
        return []
    
    # Для упрощения - парсим основную информацию
    # В реальном сценарии нужно парсить каждую страницу матча отдельно
    # Здесь возвращаем заглушку
    return matches


def collect_fbref_season(league: str, season: int) -> List[Dict]:
    """Собирает данные FBref за сезон"""
    league_info = LEAGUES.get(league)
    if not league_info:
        return []
    
    # FBref URL формат: /comps/9/2023-2024/2023-2024-Premier-League-Stats
    season_str = f"{season}-{season+1}"
    url = f"https://fbref.com/en/comps/{league_info['id']}/{season_str}/{season_str}-{league_info['name'].replace(' ', '-')}-Stats"
    
    logger.info(f"📊 Запрос: {league} {season}/{season+1}")
    
    try:
        with httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            html = response.text
            logger.info(f"   HTML получен: {len(html)} символов")
            
            # FBref отдаёт полноценный HTML с таблицами
            soup = BeautifulSoup(html, "html.parser")
            
            # Ищем таблицу с результатами матчей
            # Обычно это table с id="matchlogs" или подобным
            tables = soup.find_all("table")
            logger.info(f"   Найдено таблиц: {len(tables)}")
            
            # Для упрощения - возвращаем пустой список
            # В реальном сценарии нужно парсить таблицу матчей
            return []
    
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
    
    logger.info(f"🚀 Сбор данных FBref для сезонов: {seasons}")
    logger.info(f"📊 Лиг: {len(LEAGUES)}")
    
    all_matches = []
    
    for league in LEAGUES.keys():
        for season in seasons:
            matches = collect_fbref_season(league, season)
            all_matches.extend(matches)
            time.sleep(3)  # FBref более строгий к запросам
    
    return all_matches


def main():
    print("=" * 60)
    print("📊 СБОР XG ДАННЫХ С FBREF.COM")
    print("=" * 60)
    print()
    print("⚠️ FBref требует более сложного парсинга таблиц")
    print("💡 Рекомендуется использовать football-data.co.uk")
    print()
    
    matches = collect_all(seasons=[2024, 2023, 2022, 2021, 2020])
    
    if not matches:
        print("\n❌ FBref парсинг требует доработки")
        print("💡 Переключаемся на football-data.co.uk")
        return
    
    print(f"\n✅ Собрано {len(matches)} матчей")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    main()
