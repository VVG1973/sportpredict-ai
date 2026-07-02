import logging
import httpx
from datetime import datetime, timedelta, timezone
from database.db import Database

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


class ResultChecker:
    """Проверяет результаты завершённых матчей"""

    BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"

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

        for match in pending:
            fixture_id, home_team, away_team, match_date, prediction = match

            # Проверяем, прошёл ли матч
            try:
                match_dt = datetime.fromisoformat(match_date.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)

                # Матч должен был завершиться (прошло 3+ часа после начала)
                if now < match_dt + timedelta(hours=3):
                    continue

                # Пытаемся получить результат
                result = await self._get_match_result(home_team, away_team, match_date)

                if result:
                    # Определяем, выиграл ли прогноз
                    is_win = self._check_prediction_win(prediction, result)

                    if is_win:
                        await db.update_result(fixture_id, "win")
                        wins += 1
                        logger.info(f"✅ {home_team} vs {away_team}: ВЫИГРЫШ ({prediction})")
                    else:
                        await db.update_result(fixture_id, "loss")
                        losses += 1
                        logger.info(f"❌ {home_team} vs {away_team}: ПРОИГРЫШ ({prediction})")

                    checked += 1
                else:
                    # ❗ НЕТ РЕЗУЛЬТАТА — пропускаем, НЕ генерируем случайный
                    skipped += 1
                    logger.warning(f"⏳ {home_team} vs {away_team}: результат не найден, пропускаем")

            except Exception as e:
                logger.debug(f"Ошибка проверки {fixture_id}: {e}")
                continue

        await db.close()

        if checked > 0:
            logger.info(f"✅ Проверено {checked} матчей: {wins} выигрышей, {losses} проигрышей")
        if skipped > 0:
            logger.info(f"⏳ Пропущено {skipped} матчей (результат не найден)")
        if checked == 0 and skipped == 0:
            logger.info("⏳ Нет завершённых матчей для проверки")

    async def _get_match_result(self, home_team: str, away_team: str, match_date: str) -> str:
        """Получает результат матча из TheSportsDB"""
        try:
            # Извлекаем дату
            date_str = match_date[:10]

            url = f"{self.BASE_URL}/eventsday.php?sport=Soccer&date={date_str}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()

                    if "events" in data and data["events"]:
                        for event in data["events"]:
                            event_home = event.get("strHomeTeam", "")
                            event_away = event.get("strAwayTeam", "")

                            # Проверяем совпадение команд
                            if (home_team.lower() in event_home.lower() or event_home.lower() in home_team.lower()) and \
                               (away_team.lower() in event_away.lower() or event_away.lower() in away_team.lower()):

                                home_score = event.get("intHomeScore")
                                away_score = event.get("intAwayScore")

                                if home_score is not None and away_score is not None:
                                    try:
                                        home_score = int(home_score)
                                        away_score = int(away_score)

                                        if home_score > away_score:
                                            return "H"
                                        elif home_score < away_score:
                                            return "A"
                                        else:
                                            return "D"
                                    except (ValueError, TypeError):
                                        logger.warning(f"⚠️ Некорректные счёта: {home_score}:{away_score}")
                                        return None

            # ❗ РЕЗУЛЬТАТ НЕ НАЙДЕН — возвращаем None, НЕ случайное значение
            logger.info(f"📭 Результат не найден: {home_team} vs {away_team} ({date_str})")
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения результата: {e}")
            return None

    def _check_prediction_win(self, prediction: str, result: str) -> bool:
        """Проверяет, выиграл ли прогноз"""
        # Маппинг прогнозов
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