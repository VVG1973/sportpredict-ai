import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from config import settings

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


class SportsAPIParser:
    def __init__(self):
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        self.headers = {
            "X-RapidAPI-Key": settings.API_KEY_SPORTS,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_upcoming_matches(self, league_id: int = None, days: int = 2) -> list:
        """Получает матчи с повторными попытками (retry) при сбоях"""
        all_matches = []
        leagues_to_check = ALL_LEAGUES if league_id is None else [league_id]

        for lid in leagues_to_check:
            today = datetime.now()
            tomorrow = today + timedelta(days=days)

            url = f"{self.base_url}/fixtures"
            params = {
                "league": lid,
                "season": today.year,
                "from": today.strftime("%Y-%m-%d"),
                "to": tomorrow.strftime("%Y-%m-%d")
            }

            for attempt in range(3):
                try:
                    resp = await self.client.get(url, headers=self.headers, params=params)

                    if resp.status_code == 429:
                        logger.warning("⚠️ Превышен лимит запросов API. Ожидание 60 сек...")
                        await asyncio.sleep(60)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    if data.get("errors"):
                        logger.error(f"API вернул ошибку: {data['errors']}")
                        return []

                    matches = data.get("response", [])
                    logger.info(f"📥 Загружено {len(matches)} реальных матчей.")
                    all_matches.extend(matches)
                    return all_matches

                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP Ошибка (попытка {attempt+1}/3): {e.response.status_code}")
                except Exception as e:
                    logger.error(f"Сетевая ошибка (попытка {attempt+1}/3): {e}")

                if attempt < 2:
                    await asyncio.sleep(5)

            logger.warning(f"❌ Не удалось загрузить матчи для лиги {lid} после 3 попыток.")

        return all_matches

    async def close(self):
        await self.client.aclose()
