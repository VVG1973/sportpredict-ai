import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from config import settings

logger = logging.getLogger(__name__)

class SportsAPIParser:
    def __init__(self):
        # Используем API-Football (RapidAPI)
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        self.headers = {
            "X-RapidAPI-Key": settings.API_KEY_SPORTS,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_upcoming_matches(self, league_id: int = 39, days: int = 2) -> list:
        """Получает матчи с повторными попытками (retry) при сбоях"""
        today = datetime.now()
        tomorrow = today + timedelta(days=days)
        
        url = f"{self.base_url}/fixtures"
        params = {
            "league": league_id, # 39 = Premier League
            "season": today.year,
            "from": today.strftime("%Y-%m-%d"),
            "to": tomorrow.strftime("%Y-%m-%d")
        }

        for attempt in range(3): # 3 попытки
            try:
                resp = await self.client.get(url, headers=self.headers, params=params)
                
                # Обработка специфических ошибок API
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
                return matches

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP Ошибка (попытка {attempt+1}/3): {e.response.status_code}")
            except Exception as e:
                logger.error(f"Сетевая ошибка (попытка {attempt+1}/3): {e}")
            
            if attempt < 2:
                await asyncio.sleep(5) # Ждем 5 секунд перед повтором

        logger.critical("❌ Не удалось загрузить матчи после 3 попыток.")
        return []

    async def close(self):
        await self.client.aclose()
