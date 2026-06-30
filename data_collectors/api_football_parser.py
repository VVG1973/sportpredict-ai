"""
Парсер реальных матчей из API-Football
Получает матчи всех лиг мира (включая летние)
"""
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict
import httpx
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


logger = logging.getLogger(__name__)

# Летние лиги, которые играют в июне-июле
SUMMER_LEAGUES = {
    71: "Brazilian Serie A",      # 🇧🇷 Бразилия
    253: "MLS",                   # 🇺🇸 США
    113: "Allsvenskan",           # 🇸🇪 Швеция
    103: "Eliteserien",           # 🇳🇴 Норвегия
    98: "J1 League",              # 🇯🇵 Япония
    292: "K League 1",            # 🇰🇷 Корея
    128: "Argentine Primera",     # 🇦🇷 Аргентина
    115: "Chilean Primera",       # 🇨🇱 Чили
    78: "Liga MX",                # 🇲🇽 Мексика
    109: "Veikkausliiga",         # 🇫🇮 Финляндия
}


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
    
    def get_fixtures_by_date(self, date: str) -> List[Dict]:
        """
        Получает матчи на указанную дату
        
        Args:
            date: Дата в формате YYYY-MM-DD (например, "2026-06-29")
        
        Returns:
            Список матчей
        """
        if not self.api_key:
            logger.warning("⚠️ API ключ не установлен, возвращаем пустой список")
            return []
        
        url = f"{self.base_url}/fixtures"
        params = {"date": date}
        
        try:
            with httpx.Client(headers=self.headers, timeout=30.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("errors"):
                    logger.error(f"❌ API ошибка: {data['errors']}")
                    return []
                
                fixtures = data.get("response", [])
                logger.info(f"📅 {date}: получено {len(fixtures)} матчей из API-Football")
                
                # Фильтруем только летние лиги
                summer_fixtures = []
                for fixture in fixtures:
                    league_id = fixture.get("league", {}).get("id")
                    if league_id in SUMMER_LEAGUES:
                        summer_fixtures.append(fixture)
                
                logger.info(f"   Из них летних лиг: {len(summer_fixtures)}")
                return summer_fixtures
        
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
                
                match = {
                    "fixture_id": f"apifb_{fixture_data.get('id')}",
                    "league": league.get("name", "Unknown"),
                    "league_id": league.get("id"),
                    "date": fixture_data.get("date", "")[:10],  # YYYY-MM-DD
                    "time": fixture_data.get("date", "")[11:16],  # HH:MM
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
    
    def get_matches_for_dates(self, days_ahead: int = 3) -> List[Dict]:
        """
        Получает матчи на ближайшие N дней
        
        Args:
            days_ahead: Количество дней вперед (по умолчанию 3)
        
        Returns:
            Список всех матчей
        """
        all_matches = []
        today = datetime.now()
        
        for i in range(days_ahead):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            
            fixtures = self.get_fixtures_by_date(date_str)
            matches = self.parse_fixtures(fixtures)
            all_matches.extend(matches)
        
        logger.info(f"✅ Всего получено {len(all_matches)} реальных матчей на {days_ahead} дней")
        return all_matches
