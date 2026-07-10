"""
Парсер NHL (Национальная хоккейная лига)
Бесплатный API, без ключа: api-web.nhle.com

Запуск: из HybridSportsParser автоматически
"""
import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_URL = "https://api-web.nhle.com/v1"


class NHLParser:
    """Парсер матчей NHL через официальный API"""

    def __init__(self):
        self.base_url = BASE_URL

    async def get_schedule(self, date: str = None) -> dict:
        """Получает расписание на дату"""
        if not date:
            date = "now"

        url = f"{self.base_url}/schedule/{date}"
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"❌ Ошибка NHL API: {e}")
            return {}

    def parse_games(self, data: dict) -> List[Dict]:
        """Парсит матчи из ответа NHL API"""
        matches = []
        game_weeks = data.get("gameWeek", [])

        for week in game_weeks:
            for game in week.get("games", []):
                game_state = game.get("gameState")

                # Только запланированные или завершённые матчи
                if game_state not in ["FINAL", "OFF"]:
                    # Проверяем дату - если матч сегодня или завтра
                    start_time = game.get("startTimeUTC", "")
                    if start_time:
                        try:
                            game_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                            now = datetime.now(game_dt.tzinfo)
                            # Берём матчи на сегодня и завтра
                            if game_dt.date() > now.date() + timedelta(days=1):
                                continue
                        except:
                            continue

                home_team = game.get("homeTeam", {})
                away_team = game.get("awayTeam", {})

                home_name = home_team.get("commonName", {}).get("default", "")
                away_name = away_team.get("commonName", {}).get("default", "")
                home_place = home_team.get("placeName", {}).get("default", "")
                away_place = away_team.get("placeName", {}).get("default", "")

                # Формируем полное название
                home_full = f"{home_place} {home_name}" if home_place else home_name
                away_full = f"{away_place} {away_name}" if away_place else away_name

                home_score = home_team.get("score", 0) or 0
                away_score = away_team.get("score", 0) or 0

                # Определяем результат
                if game_state in ["FINAL", "OFF"]:
                    if home_score > away_score:
                        result = "H"
                    elif home_score < away_score:
                        result = "A"
                    else:
                        result = "D"
                else:
                    result = ""

                # Дата матча
                game_date = game.get("date", "")

                matches.append({
                    "fixture_id": f"nhl_{game.get('id', 0)}",
                    "date": game_date,
                    "league_name": "NHL",
                    "home_team": home_full,
                    "away_team": away_full,
                    "home_goals": home_score,
                    "away_goals": away_score,
                    "result": result,
                    "B365H": 0,
                    "B365D": 0,
                    "B365A": 0,
                    "HS": 0,
                    "AS": 0,
                    "HST": 0,
                    "AST": 0,
                    "HC": 0,
                    "AC": 0,
                    "sport": "🏒 Хоккей",
                    "is_real": True,
                })

        return matches

    async def get_upcoming_matches(self, days_ahead: int = 2) -> List[Dict]:
        """Получает предстоящие матчи NHL"""
        all_matches = []

        for day_offset in range(days_ahead):
            date = (datetime.now() + timedelta(days=day_offset)).strftime("%Y-%m-%d")

            data = await self.get_schedule(date)
            if data:
                matches = self.parse_games(data)
                all_matches.extend(matches)

            await asyncio.sleep(0.3)

        logger.info(f"🏒 NHL: получено {len(all_matches)} матчей")
        return all_matches
