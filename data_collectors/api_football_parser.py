"""
Парсер реальных матчей из API-Football
Поддерживает: футбол, хоккей, теннис, киберспорт
"""
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict
import httpx
import asyncio

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# ЛИГИ ПО ВИДАМ СПОРТА
# ═══════════════════════════════════════════════════════

# Футбол (все лиги — основные + летние)
FOOTBALL_LEAGUES = [
    39, 140, 135, 78, 61, 88, 94, 235, 71, 7, 1, 2, 3,
    113, 103, 98, 292, 128, 115, 36, 109,
]

# Хоккей (НХЛ, КХЛ, Шведская лига, Финская, Чешская, и т.д.)
HOCKEY_LEAGUES = [
    1,    # NHL
    2,    # KHL
    8,    # SHL (Швеция)
    9,    # Liiga (Финляндия)
    10,   # Extraliga (Чехия)
    11,   # National League (Швейцария)
    12,   # DEL (Германия)
    13,   # ICEHL (Австрия)
    14,   # MHL (Россия)
    16,   # OHL (Канада)
    17,   # QMJHL (Канада)
    18,   # WHL (Канада)
    72,   # Liiga (Финляндия)
    112,  # AHL (США)
    113,  # ECHL (США)
]

# Теннис (ATP, WTA, ITF)
TENNIS_LEAGUES = [
    1,    # ATP Masters 1000
    2,    # ATP 500
    3,    # ATP 250
    4,    # WTA 1000
    5,    # WTA 500
    6,    # WTA 250
    7,    # Grand Slam
    8,    # ATP Challenger
    9,    # ITF Men
    10,   # ITF Women
]

# Киберспорт (ESL, DreamHack, и т.д.)
ESPORTS_LEAGUES = [
    1,    # ESL Pro League
    2,    # ESL One
    3,    # DreamHack
    4,   # BLAST Premier
    5,   # IEM
    6,   # PGL
    7,   # ESEA
    8,   # FACEIT
]

# Все лиги вместе
ALL_LEAGUES = FOOTBALL_LEAGUES + HOCKEY_LEAGUES + TENNIS_LEAGUES + ESPORTS_LEAGUES

# Маппинг: ID лиги -> вид спорта
LEAGUE_SPORT_MAP = {}
for lid in FOOTBALL_LEAGUES:
    LEAGUE_SPORT_MAP[lid] = "⚽ Футбол"
for lid in HOCKEY_LEAGUES:
    LEAGUE_SPORT_MAP[lid] = "🏒 Хоккей"
for lid in TENNIS_LEAGUES:
    LEAGUE_SPORT_MAP[lid] = "🎾 Теннис"
for lid in ESPORTS_LEAGUES:
    LEAGUE_SPORT_MAP[lid] = "🎮 Киберспорт"


class APIFootballParser:
    """Парсер матчей из API-Football"""
    
    def __init__(self):
        self.api_key = os.getenv("API_FOOTBALL_KEY")
        if not self.api_key:
            logger.warning("⚠️ API_FOOTBALL_KEY не найден в переменных окружения")
        
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "x-apisports-key": self.api_key,
            "x-rapidapi-host": "v3.football.api-sports.io"
        }
    
    async def get_fixtures_by_date(self, date: str, sport: str = "football") -> List[Dict]:
        """Получает матчи на указанную дату для указанного вида спорта"""
        if not self.api_key:
            logger.warning("⚠️ API ключ не установлен")
            return []

        # Определяем лиги для данного вида спорта
        if sport == "hockey":
            target_leagues = HOCKEY_LEAGUES
        elif sport == "tennis":
            target_leagues = TENNIS_LEAGUES
        elif sport == "esports":
            target_leagues = ESPORTS_LEAGUES
        else:
            target_leagues = FOOTBALL_LEAGUES

        url = f"{self.base_url}/fixtures"
        params = {"date": date}

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("errors"):
                    logger.error(f"❌ API ошибка: {data['errors']}")
                    return []

                fixtures = data.get("response", [])

                # Фильтруем по нужным лигам
                filtered = []
                for fixture in fixtures:
                    league_id = fixture.get("league", {}).get("id")
                    if league_id in target_leagues:
                        filtered.append(fixture)

                sport_emoji = {"football": "⚽", "hockey": "🏒", "tennis": "🎾", "esports": "🎮"}.get(sport, "⚽")
                logger.info(f"📅 {sport_emoji} {date}: {len(filtered)}/{len(fixtures)} матчей ({sport})")
                return filtered

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("❌ Превышен лимит запросов (100/день)")
            else:
                logger.error(f"❌ HTTP ошибка: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка запроса: {e}")
            return []
    
    def parse_fixtures(self, fixtures: List[Dict]) -> List[Dict]:
        """
        Преобразует данные API-Football в формат приложения
        
        Args:
            fixtures: Список матчей из API
        
        Returns:
            Список матчей в формате приложения
        """
        matches = []
        
        for fixture in fixtures:
            try:
                fixture_data = fixture.get("fixture", {})
                teams = fixture.get("teams", {})
                league = fixture.get("league", {})
                odds = fixture.get("odds", [])
                
                # Извлекаем коэффициенты (если есть)
                home_odds = 0.0
                draw_odds = 0.0
                away_odds = 0.0
                
                if odds and len(odds) > 0:
                    # Ищем коэффициенты 1X2
                    for odd in odds:
                        if odd.get("bookmaker"):
                            values = odd.get("values", [])
                            for value in values:
                                if value.get("value") == "Home":
                                    home_odds = float(value.get("odd", 0))
                                elif value.get("value") == "Draw":
                                    draw_odds = float(value.get("odd", 0))
                                elif value.get("value") == "Away":
                                    away_odds = float(value.get("odd", 0))
                            break
                
                # Определяем вид спорта по ID лиги
                league_id = league.get("id")
                sport = LEAGUE_SPORT_MAP.get(league_id, "⚽ Футбол")

                match = {
                    "fixture_id": f"apifb_{fixture_data.get('id')}",
                    "league": league.get("name", "Unknown"),
                    "league_id": league_id,
                    "sport": sport,
                    "date": fixture_data.get("date", "")[:10],
                    "time": fixture_data.get("date", "")[11:16],
                    "home_team": teams.get("home", {}).get("name", ""),
                    "away_team": teams.get("away", {}).get("name", ""),
                    "home_odds": home_odds,
                    "draw_odds": draw_odds,
                    "away_odds": away_odds,
                    "is_real": True,
                }
                
                matches.append(match)
            
            except Exception as e:
                logger.debug(f"Пропуск матча: {e}")
                continue
        
        return matches
    
    async def get_matches_for_dates(self, days_ahead: int = 3) -> List[Dict]:
        """Получает матчи ВСЕХ видов спорта на ближайшие N дней"""
        all_matches = []
        today = datetime.now()

        sports = ["football", "hockey", "tennis"]

        for i in range(days_ahead):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")

            for sport in sports:
                fixtures = await self.get_fixtures_by_date(date_str, sport=sport)
                matches = self.parse_fixtures(fixtures)
                all_matches.extend(matches)
                await asyncio.sleep(0.3)

        logger.info(f"✅ Всего: {len(all_matches)} матчей (футбол + хоккей + теннис) на {days_ahead} дней")
        return all_matches
