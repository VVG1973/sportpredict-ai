import sys
import os
# Добавляем корень проекта в пути импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


import httpx
import pandas as pd
import asyncio
import logging
import random
from datetime import datetime
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class HistoricalDataLoader:
    def __init__(self):
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        self.headers = {
            "X-RapidAPI-Key": settings.API_KEY_SPORTS,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        self.client = httpx.AsyncClient(timeout=60.0)
        
    async def fetch_season_fixtures(self, league_id: int, season: int) -> list:
        """Загружает все матчи сезона"""
        url = f"{self.base_url}/fixtures"
        params = {"league": league_id, "season": season}
        
        try:
            resp = await self.client.get(url, headers=self.headers, params=params)
            
            if resp.status_code == 401 or resp.status_code == 403:
                logger.error("❌ Неверный или отсутствует API_KEY_SPORTS в .env!")
                logger.error("💡 Получите ключ на https://rapidapi.com/api-sports/api/api-football")
                return []
            
            if resp.status_code == 429:
                logger.error("❌ Превышен лимит запросов API (100/день на бесплатном тарифе)")
                return []
            
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("errors"):
                logger.error(f"API Error: {data['errors']}")
                return []
                
            fixtures = data.get("response", [])
            logger.info(f"📥 Загружено {len(fixtures)} матчей сезона {season}")
            return fixtures
        except Exception as e:
            logger.error(f"Ошибка загрузки сезона {season}: {e}")
            return []
    
    def extract_features(self, fixture: dict) -> dict:
        """Извлекает признаки из матча"""
        goals = fixture.get("goals", {})
        home_goals = goals.get("home", 0)
        away_goals = goals.get("away", 0)
        
        # Определяем результат: 0=HOME, 1=DRAW, 2=AWAY
        if home_goals > away_goals:
            result = 0
        elif home_goals < away_goals:
            result = 2
        else:
            result = 1
            
        return {
            "fixture_id": fixture["fixture"]["id"],
            "home_team": fixture["teams"]["home"]["name"],
            "away_team": fixture["teams"]["away"]["name"],
            "date": fixture["fixture"]["date"],
            # Для MVP используем случайные значения (в продакшене парсим последние 5 игр)
            "home_form": random.uniform(0.3, 0.8),
            "away_form": random.uniform(0.3, 0.8),
            "h2h_home_win": random.uniform(0.2, 0.7),
            "home_streak": random.randint(-3, 5),
            "key_injuries": random.choice([0, 1]),
            "home_goals": home_goals,
            "away_goals": away_goals,
            "result": result
        }
    
    async def load_history(self, league_id: int = None  # Will iterate over ALL_LEAGUES, season: int = 2024):
        """Загружает историю за 1 сезон (экономим лимит API)"""
        logger.info(f"🔄 Загрузка сезона {season}...")
        fixtures = await self.fetch_season_fixtures(league_id, season)
        
        if not fixtures:
            logger.error("❌ Не удалось загрузить матчи. Проверьте API_KEY_SPORTS в .env")
            return None
        
        all_matches = []
        for fixture in fixtures:
            status = fixture["fixture"]["status"]["short"]
            if status not in ["FT", "AET", "PEN"]:
                continue
            
            match_data = self.extract_features(fixture)
            all_matches.append(match_data)
        
        df = pd.DataFrame(all_matches)
        
        # Создаём папку data, если её нет
        os.makedirs("data", exist_ok=True)
        df.to_csv("data/historical_matches.csv", index=False)
        logger.info(f"✅ Сохранено {len(df)} матчей в data/historical_matches.csv")
        return df

async def main():
    loader = HistoricalDataLoader()
    await loader.load_history()

if __name__ == "__main__":
    asyncio.run(main())
