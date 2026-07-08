import os
import logging
import httpx
from datetime import datetime, timedelta, timezone
from database.db import Database
from config import settings

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


class ResultChecker:
    """Проверяет результаты завершённых матчей через API-Football"""

    BASE_URL = "https://v3.football.api-sports.io"

    async def run(self):
        """Основной метод проверки"""
        logger.info("🔍 Начинаю проверку результатов матчей...")

        db = Database()
        await db.init()

        pending = await db.get_pending_predictions()

        if not pending:
            logger.info("⏳ Нет матчей для проверки")
            await db.close()
            return

        logger.info(f"📋 Проверяю {len(pending)} матчей")

        checked = 0
        wins = 0
        losses = 0
        skipped = 0
        not_finished = 0

        for match in pending:
            fixture_id, home_team, away_team, match_date, prediction = match

            try:
                # Проверяем, прошёл ли матч (2+ часа после начала)
                match_dt = datetime.fromisoformat(match_date.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                
                if now < match_dt + timedelta(hours=2):
                    not_finished += 1
                    continue

                # Получаем результат по fixture_id через API-Football
                result = await self._get_match_result(fixture_id)

                if result:
                    is_win = self._check_prediction_win(prediction, result)

                    if is_win:
                        await db.update_result(fixture_id, 'win')
                        wins += 1
                        logger.info(f"✅ {home_team} vs {away_team}: ВЫИГРЫШ ({prediction})")
                    else:
                        await db.update_result(fixture_id, 'loss')
                        losses += 1
                        logger.info(f"❌ {home_team} vs {away_team}: ПРОИГРЫШ ({prediction})")

                    checked += 1
                else:
                    # Матч ещё не завершён или результат недоступен
                    skipped += 1
                    logger.debug(f"⏳ {home_team} vs {away_team}: результат недоступен")

            except Exception as e:
                logger.error(f"❌ Ошибка проверки {fixture_id}: {e}")
                continue

        await db.close()

        logger.info(f"📊 Итоги: проверено {checked}, выигрышей {wins}, проигрышей {losses}, пропущено {skipped}, не завершены {not_finished}")

    async def _get_match_result(self, fixture_id: str) -> str:
        """Получает результат матча по fixture_id из API-Football"""
        try:
            url = f"{self.BASE_URL}/fixtures"
            headers = {"x-apisports-key": settings.API_FOOTBALL_KEY}
            params = {"id": fixture_id}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code != 200:
                    logger.warning(f"⚠️ API вернул статус {response.status_code}")
                    return None

                data = response.json()
                
                if not data.get("response"):
                    logger.debug(f"📭 Матч {fixture_id} не найден в API")
                    return None

                fixture = data["response"][0]
                status = fixture["fixture"]["status"]["short"]
                
                # Проверяем, завершён ли матч
                if status not in ["FT", "AET", "PEN"]:
                    logger.debug(f"⏳ Матч {fixture_id} ещё не завершён (статус: {status})")
                    return None

                goals = fixture.get("goals", {})
                home = goals.get("home")
                away = goals.get("away")

                if home is None or away is None:
                    logger.warning(f"⚠️ Счёт недоступен для {fixture_id}")
                    return None

                if home > away:
                    return "H"
                elif home < away:
                    return "A"
                else:
                    return "D"

        except Exception as e:
            logger.error(f"❌ Ошибка получения результата: {e}")
            return None

    def _check_prediction_win(self, prediction: str, result: str) -> bool:
        """Проверяет, выиграл ли прогноз"""
        prediction_map = {
            "П1": "H",
            "X": "D",
            "П2": "A",
            "H": "H",
            "D": "D",
            "A": "A"
        }

        predicted_result = prediction_map.get(prediction, prediction)
        return predicted_result == result