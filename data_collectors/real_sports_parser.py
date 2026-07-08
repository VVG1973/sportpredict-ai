import os
import logging
import httpx
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

        matches = matches[:count]
        logger.info(f"✅ Получено {len(matches)} реальных матчей")
        return matches

    async def get_match_odds(self, fixture_id: str) -> Dict:
        """Получает коэффициенты матча из API-Football"""
        api_key = os.environ.get("API_FOOTBALL_KEY", "")
        if not api_key:
            logger.warning("API_FOOTBALL_KEY не установлен, коэффициенты недоступны")
            return {}

        url = "https://v3.football.api-sports.io/odds"
        headers = {"x-apisports-key": api_key}
        params = {"fixture": fixture_id, "bookmaker": 1}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)
                data = response.json()

                odds_data = data["response"][0]["bookmakers"][0]["bets"]

                result = {
                    "home": 0, "draw": 0, "away": 0,
                    "over_2_5": 0, "under_2_5": 0,
                    "both_yes": 0, "both_no": 0,
                    "handicap_home": 0, "handicap_away": 0,
                }

                for bet in odds_data:
                    bet_name = bet["name"]
                    values = bet["values"]

                    if bet_name == "Match Winner":
                        for v in values:
                            if v["value"] == "Home": result["home"] = float(v["odd"])
                            elif v["value"] == "Draw": result["draw"] = float(v["odd"])
                            elif v["value"] == "Away": result["away"] = float(v["odd"])

                    elif bet_name == "Over/Under 2.5":
                        for v in values:
                            if v["value"] == "Over": result["over_2_5"] = float(v["odd"])
                            elif v["value"] == "Under": result["under_2_5"] = float(v["odd"])

                    elif bet_name == "Both Teams Score":
                        for v in values:
                            if v["value"] == "Yes": result["both_yes"] = float(v["odd"])
                            elif v["value"] == "No": result["both_no"] = float(v["odd"])

                    elif bet_name == "Asian Handicap":
                        for v in values:
                            if v["value"].startswith("Home"): result["handicap_home"] = float(v["odd"])
                            elif v["value"].startswith("Away"): result["handicap_away"] = float(v["odd"])

                return result

        except Exception as e:
            logger.error(f"Ошибка получения коэффициентов: {e}")
            return {}

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
                except ValueError:
                    match_datetime = datetime.now() + timedelta(hours=48)
            else:
                match_datetime = datetime.now() + timedelta(hours=48)

            # ❗ УБРАНЫ СЛУЧАЙНЫЕ ПРОГНОЗЫ
            # Прогноз будет сделан позже ML-моделью
            # Здесь только собираем данные о матче

            return {
                "fixture": {
                    "id": int(event.get("idEvent", 0)),
                    "date": match_datetime.isoformat()
                },
                "teams": {
                    "home": {"name": home_team},
                    "away": {"name": away_team}
                },
                "sport": "⚽ Футбол",
                "league": league_name,
                # ❗ НЕТ случайного outcome, confidence, odds
                # Эти поля будут заполнены ML-моделью в main.py
                "is_real": True
            }
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования матча: {e}")
            return None


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

        # ❗ УБРАНО: добавление mock-матчей для "разнообразия"
        # Если реальных матчей мало — просто возвращаем то, что есть
        # ML-модель должна работать только с реальными данными

        logger.info(f"✅ Всего матчей: {len(real_matches)} (только реальные)")
        return real_matches