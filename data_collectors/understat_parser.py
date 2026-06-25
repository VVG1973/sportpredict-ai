"""
Парсер xG данных с Understat.com
Поддерживает: EPL, La Liga, Serie A, Bundesliga, Ligue 1
"""
import asyncio
import json
import aiohttp
from pathlib import Path
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class UnderstatParser:
    """Парсер xG данных с Understat"""
    
    BASE_URL = "https://understat.com"
    LEAGUES = {
        "EPL": "EPL",
        "La_liga": "La_liga",
        "Serie_A": "Serie_A",
        "Bundesliga": "Bundesliga",
        "Ligue_1": "Ligue_1"
    }
    
    def __init__(self, cache_dir: str = "data/historical/xg"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def fetch_league_data(self, league: str, season: str = "2023") -> list:
        """Скачивает xG данные для лиги и сезона"""
        cache_file = self.cache_dir / f"{league}_{season}.json"
        
        # Проверяем кэш
        if cache_file.exists():
            logger.info(f"📦 Загружаю {league} {season} из кэша")
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        logger.info(f"🌐 Скачиваю {league} {season} с Understat...")
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/league/{self.LEAGUES[league]}/{season}"
                
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"❌ Ошибка HTTP {response.status} для {league}")
                        return []
                    
                    html = await response.text()
                    
                    # Understat использует JSON в HTML
                    dates_data = re.search(r"datesData\s*=\s*JSON\.parse\('(.+?)'\)", html)
                    
                    if not dates_data:
                        logger.error(f"❌ Не удалось найти datesData для {league}")
                        return []
                    
                    # Декодируем JSON
                    matches_json = dates_data.group(1).encode().decode("unicode_escape")
                    matches = json.loads(matches_json)
                    
                    # Сохраняем в кэш
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(matches, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"✅ Скачано {len(matches)} матчей для {league} {season}")
                    return matches
                    
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания {league}: {e}")
            return []
    
    async def fetch_all_leagues(self, seasons: list = None) -> dict:
        """Скачивает данные для всех лиг"""
        if seasons is None:
            current_year = datetime.now().year
            seasons = [str(current_year - i) for i in range(3)]
        
        all_data = {}
        
        for league in self.LEAGUES.keys():
            all_data[league] = {}
            for season in seasons:
                data = await self.fetch_league_data(league, season)
                if data:
                    all_data[league][season] = data
        
        return all_data


async def main():
    """Тестовая функция"""
    parser = UnderstatParser()
    
    # Скачиваем данные для EPL 2023
    matches = await parser.fetch_league_data("EPL", "2023")
    
    if matches:
        print(f"✅ Извлечено {len(matches)} матчей с xG данными")
        
        # Пример первых 3 матчей
        for i, match in enumerate(matches[:3]):
            home = match["h"]["title"]
            away = match["a"]["title"]
            home_xg = float(match["xG"].get("h", 0))
            away_xg = float(match["xG"].get("a", 0))
            home_goals = int(match["goals"].get("h", 0))
            away_goals = int(match["goals"].get("a", 0))
            
            print(f"\nМатч {i+1}:")
            print(f"  {home} vs {away}")
            print(f"  xG: {home_xg:.2f} - {away_xg:.2f}")
            print(f"  Голы: {home_goals} - {away_goals}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
