import logging
import httpx
import random
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)


class RealSportsParser:
    """Парсер реальных спортивных данных с TheSportsDB API"""
    
    BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"
    
    LEAGUES = {
        "English Premier League": "4328",
        "Spanish La Liga": "4335",
        "Italian Serie A": "4332",
        "German Bundesliga": "4331",
        "French Ligue 1": "4334",
        "Russian Premier League": "4354",
        "UEFA Champions League": "4480",
    }
    
    TEAM_MAPPING = {
        "Manchester United": "Man United",
        "Manchester City": "Man City",
        "Wolverhampton Wanderers": "Wolves",
        "West Ham": "West Ham",
        "Tottenham": "Tottenham",
        "Newcastle": "Newcastle",
        "Sheffield United": "Sheffield United",
        "Nottingham Forest": "Nott'm Forest",
        "Brighton": "Brighton",
        "Ipswich": "Ipswich",
        "Leicester": "Leicester",
        "Real Madrid": "Real Madrid",
        "Barcelona": "Barcelona",
        "Atletico Madrid": "Ath Madrid",
        "Athletic Bilbao": "Ath Bilbao",
        "Real Betis": "Betis",
        "Real Sociedad": "Real Sociedad",
        "Celta Vigo": "Celta",
        "Deportivo Alaves": "Alaves",
        "AC Milan": "Milan",
        "Inter Milan": "Inter",
        "Juventus": "Juventus",
        "Napoli": "Napoli",
        "Roma": "Roma",
        "Lazio": "Lazio",
        "Fiorentina": "Fiorentina",
        "Atalanta": "Atalanta",
        "Bayern Munich": "Bayern Munich",
        "Borussia Dortmund": "Dortmund",
        "Bayer Leverkusen": "Leverkusen",
        "RB Leipzig": "RB Leipzig",
        "Eintracht Frankfurt": "Ein Frankfurt",
        "Paris Saint Germain": "Paris SG",
        "Olympique Marseille": "Marseille",
        "Olympique Lyonnais": "Lyon",
        "Monaco": "Monaco",
        "Zenit St Petersburg": "Zenit",
        "Spartak Moscow": "Spartak Moscow",
        "CSKA Moscow": "CSKA Moscow",
        "Lokomotiv Moscow": "Lokomotiv Moscow",
        "Dinamo Moscow": "Dinamo Moscow",
        "FC Krasnodar": "Krasnodar",
    }
    
    def __init__(self, min_confidence: float = 0.70, use_proxy: bool = False):
        self.min_confidence = min_confidence
        self.use_proxy = use_proxy
        self.proxy_url = None
    
    async def _make_request(self, url: str) -> dict:
        """Делает HTTP-запрос с защитой от пустых ответов API"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                text = response.text.strip()
                if not text:
                    return {}
                return response.json()
        except Exception as e:
            logger.debug(f"⚠️ Нет данных или ошибка JSON для {url}")
            return {}
    
    def _map_team_name(self, thesportsdb_name: str) -> str:
        """Конвертирует название команды из TheSportsDB в формат football-data.org"""
        return self.TEAM_MAPPING.get(thesportsdb_name, thesportsdb_name)
    
    async def fetch_upcoming_matches(self, count: int = 10) -> List[Dict]:
        """Получает реальные матчи из TheSportsDB API"""
        logger.info(f"🌐 Запрос реальных матчей из TheSportsDB API...")
        
        matches = []
        today = datetime.now()
        
        for day_offset in range(7):
            date_str = (today + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            
            for league_name in list(self.LEAGUES.keys())[:3]:
                url = f"{self.BASE_URL}/eventsday.php?league={league_name}&sport=Soccer&date={date_str}"
                data = await self._make_request(url)
                
                if data and "events" in data and data["events"]:
                    for event in data["events"][:2]:
                        match = self._format_match(event, league_name)
                        if match:
                            matches.append(match)
                
                await asyncio.sleep(0.5)
        
        if len(matches) < count:
            logger.info(f"⚠️ Получено только {len(matches)} реальных матчей, добавляем Mock...")
            mock_matches = await self._generate_mock_matches(count - len(matches))
            matches.extend(mock_matches)
        
        matches = matches[:count]
        logger.info(f"✅ Получено {len(matches)} матчей (реальных + mock)")
        return matches
    
    def _format_match(self, event: dict, league_name: str) -> Dict:
        """Форматирует матч из API в нужный формат"""
        try:
            home_team_raw = event.get("strHomeTeam", "Команда 1")
            away_team_raw = event.get("strAwayTeam", "Команда 2")
            
            home_team = self._map_team_name(home_team_raw)
            away_team = self._map_team_name(away_team_raw)
            
            date_str = event.get("dateEvent", "")
            time_str = event.get("strTime", "00:00:00")
            
            if date_str and time_str:
                try:
                    match_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                except:
                    match_datetime = datetime.now() + timedelta(hours=random.randint(2, 72))
            else:
                match_datetime = datetime.now() + timedelta(hours=random.randint(2, 72))
            
            confidence = round(random.uniform(0.70, 0.85), 2)
            odds = self._generate_odds(confidence)
            
            outcomes = ["П1", "X", "П2", "ТБ 2.5", "ТМ 2.5"]
            prediction = random.choice(outcomes)
            
            return {
                "fixture": {
                    "id": int(event.get("idEvent", random.randint(10000, 99999))),
                    "date": match_datetime.isoformat()
                },
                "teams": {
                    "home": {"name": home_team},
                    "away": {"name": away_team}
                },
                "sport": "⚽ Футбол",
                "league": league_name,
                "outcome": prediction,
                "confidence": confidence,
                "odds": odds,
                "is_real": True
            }
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования матча: {e}")
            return None
    
    def _generate_odds(self, confidence: float) -> float:
        if confidence >= 0.85:
            return round(random.uniform(1.40, 1.80), 2)
        elif confidence >= 0.78:
            return round(random.uniform(1.75, 2.30), 2)
        else:
            return round(random.uniform(2.20, 3.20), 2)
    
    async def _generate_mock_matches(self, count: int) -> List[Dict]:
        """Генерирует Mock-матчи с РЕАЛЬНЫМИ названиями команд"""
        from data_collectors.multi_sport_parser import MultiSportParser
        mock_parser = MultiSportParser(min_confidence=self.min_confidence)
        matches = await mock_parser.fetch_upcoming_matches(count=count)
        
        for match in matches:
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            match["teams"]["home"]["name"] = self._map_team_name(home)
            match["teams"]["away"]["name"] = self._map_team_name(away)
        
        return matches


class HybridSportsParser:
    """Гибридный парсер: реальные данные + Mock для разнообразия"""
    
    def __init__(self, min_confidence: float = 0.70, real_data_ratio: float = 0.6):
        self.min_confidence = min_confidence
        self.real_data_ratio = real_data_ratio
        self.real_parser = RealSportsParser(min_confidence=min_confidence)
    
    async def fetch_upcoming_matches(self, count: int = 20) -> List[Dict]:
        real_count = int(count * self.real_data_ratio)
        mock_count = count - real_count
        
        # Распределяем: 60% футбол, 25% киберспорт, 15% другие
        football_count = int(real_count * 0.60)
        esports_count = int(real_count * 0.25)
        other_count = real_count - football_count - esports_count
        
        logger.info(f"🔄 Гибридный режим: {football_count} футбол + {esports_count} киберспорт + {other_count} другие + {mock_count} mock")
        
        # Получаем футбольные матчи
        real_matches = await self.real_parser.fetch_upcoming_matches(count=football_count)
        
        # Получаем киберспортивные матчи
        try:
            from data_collectors.esports_parser import EsportsParser
            esports_parser = EsportsParser(min_confidence=self.min_confidence)
            esports_matches = await esports_parser.fetch_esports_matches(count=esports_count)
            real_matches.extend(esports_matches)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить киберспортивные матчи: {e}")
        
        # Добавляем mock для разнообразия (теннис, баскетбол, хоккей, MMA)
        if len(real_matches) < count:
            mock_needed = count - len(real_matches)
            from data_collectors.multi_sport_parser import MultiSportParser
            mock_parser = MultiSportParser(min_confidence=self.min_confidence)
            mock_matches = await mock_parser.fetch_upcoming_matches(count=mock_needed)
            real_matches.extend(mock_matches)
        
        random.shuffle(real_matches)
        return real_matches[:count]
