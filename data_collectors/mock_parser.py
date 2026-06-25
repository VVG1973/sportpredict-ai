import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MockSportsParser:
    """Парсер с тестовыми данными для отладки без API"""
    
    async def fetch_upcoming_matches(self, league_id: int = 39, days: int = 3) -> list:
        """Возвращает 2 тестовых матча"""
        logger.info("🎭 Используем Mock-данные (тестовый режим)")
        
        base_date = datetime.now()
        return [
            {
                "fixture": {"id": 1001, "date": (base_date + timedelta(hours=2)).isoformat()},
                "league": {"id": league_id, "name": "Premier League", "country": "England"},
                "teams": {
                    "home": {"id": 33, "name": "Manchester United"},
                    "away": {"id": 40, "name": "Liverpool"}
                },
                "goals": {"home": None, "away": None},
                "score": {"halftime": {"home": None, "away": None}, "fulltime": {"home": None, "away": None}}
            },
            {
                "fixture": {"id": 1002, "date": (base_date + timedelta(days=1, hours=18)).isoformat()},
                "league": {"id": league_id, "name": "Premier League", "country": "England"},
                "teams": {
                    "home": {"id": 50, "name": "Manchester City"},
                    "away": {"id": 42, "name": "Arsenal"}
                },
                "goals": {"home": None, "away": None},
                "score": {"halftime": {"home": None, "away": None}, "fulltime": {"home": None, "away": None}}
            }
        ]
