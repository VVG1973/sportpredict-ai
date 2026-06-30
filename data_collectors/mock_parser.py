import logging
from datetime import datetime, timedelta
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

class MockSportsParser:
    """Парсер с тестовыми данными для отладки без API"""
    
    async def fetch_upcoming_matches(self, league_id: int = None  # Will iterate over ALL_LEAGUES, days: int = 3) -> list:
        all_matches = []
        leagues_to_check = ALL_LEAGUES if league_id is None else [league_id]
        for league_id in leagues_to_check:
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

            all_matches.extend(matches)
        return all_matches
