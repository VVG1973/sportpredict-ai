"""
Скрипт сбора исторических данных для хоккея и тенниса
Использует API-Football для получения завершённых матчей с коэффициентами и статистикой.

Запуск: python scripts/collect_hockey_tennis.py
Лимит: 100 запросов/день (Free план)
"""
import asyncio
import httpx
import json
import logging
import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ ЛИГ
# ═══════════════════════════════════════════════════════

HOCKEY_LEAGUES = {
    1: "NHL",
    2: "KHL",
    8: "SHL (Sweden)",
    9: "Liiga (Finland)",
    10: "Extraliga (Czech)",
    11: "National League (Switzerland)",
    12: "DEL (Germany)",
}

TENNIS_LEAGUES = {
    1: "ATP Masters 1000",
    2: "ATP 500",
    3: "ATP 250",
    4: "WTA 1000",
    5: "WTA 500",
    6: "WTA 250",
    7: "Grand Slam",
}

BASE_URL = "https://v3.football.api-sports.io"


class HockeyTennisCollector:
    def __init__(self):
        self.api_key = os.environ.get("API_FOOTBALL_KEY", "")
        if not self.api_key:
            raise ValueError("API_FOOTBALL_KEY не установлен!")

        self.headers = {
            "x-apisports-key": self.api_key,
            "x-rapidapi-host": "v3.football.api-sports.io"
        }
        self.data_dir = Path("data/historical")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.request_count = 0

    async def _request(self, url: str, params: dict = None) -> dict:
        """Делает запрос с обработкой лимитов"""
        self.request_count += 1

        if self.request_count >= 95:
            logger.warning("⚠️ Приближаемся к лимиту запросов (95/100). Останавливаю.")
            return {"error": "rate_limit"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params or {})

                if response.status_code == 429:
                    logger.warning("⚠️ Лимит запросов! Жду 60 секунд...")
                    await asyncio.sleep(60)
                    return await self._request(url, params)

                response.raise_for_status()
                data = response.json()

                if data.get("errors"):
                    logger.error(f"❌ API ошибка: {data['errors']}")
                    return {"error": data["errors"]}

                return data.get("response", [])

        except Exception as e:
            logger.error(f"❌ Ошибка запроса: {e}")
            return {"error": str(e)}

    async def get_finished_fixtures(self, league_id: int, season: int) -> list:
        """Получает завершённые матчи лиги"""
        url = f"{BASE_URL}/fixtures"
        params = {
            "league": league_id,
            "season": season,
            "status": "FT"
        }
        return await self._request(url, params)

    async def get_fixture_statistics(self, fixture_id: int) -> dict:
        """Получает статистику матча (удары, угловые и т.д.)"""
        url = f"{BASE_URL}/fixtures/statistics"
        params = {"fixture": fixture_id}
        return await self._request(url, params)

    async def get_fixture_odds(self, fixture_id: int) -> dict:
        """Получает коэффициенты матча"""
        url = f"{BASE_URL}/odds"
        params = {"fixture": fixture_id}
        return await self._request(url, params)

    def extract_features(self, fixture: dict, stats: list, odds: list) -> dict:
        """Извлекает фичи из матча в формате, понятном модели"""
        fixture_data = fixture.get("fixture", {})
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})

        # Определяем результат
        home_goals = goals.get("home", 0) or 0
        away_goals = goals.get("away", 0) or 0

        if home_goals > away_goals:
            result = "H"
        elif home_goals < away_goals:
            result = "A"
        else:
            result = "D"

        # Извлекаем статистику
        home_stats = {}
        away_stats = {}
        for s in stats:
            if s.get("team", {}).get("id") == teams.get("home", {}).get("id"):
                home_stats = {item["type"]: item["value"] for item in s.get("statistics", [])}
            elif s.get("team", {}).get("id") == teams.get("away", {}).get("id"):
                away_stats = {item["type"]: item["value"] for item in s.get("statistics", [])}

        # Парсим статистику
        def parse_stat(val):
            if val is None:
                return 0
            try:
                return int(str(val).replace("%", "").strip())
            except:
                return 0

        home_shots = parse_stat(home_stats.get("Total Shots"))
        away_shots = parse_stat(away_stats.get("Total Shots"))
        home_shots_on_target = parse_stat(home_stats.get("Shots on Goal"))
        away_shots_on_target = parse_stat(away_stats.get("Shots on Goal"))
        home_corners = parse_stat(home_stats.get("Corner Kicks"))
        away_corners = parse_stat(away_stats.get("Corner Kicks"))

        # Извлекаем коэффициенты (Bet365 = bookmaker_id 1)
        home_odds = 0
        draw_odds = 0
        away_odds = 0

        for odd in odds:
            if isinstance(odd, dict) and odd.get("bookmaker", {}).get("id") == 6:  # Bet365
                for bet in odd.get("bets", []):
                    if bet.get("name") == "Match Winner":
                        for v in bet.get("values", []):
                            if v.get("value") == "Home":
                                home_odds = float(v.get("odd", 0))
                            elif v.get("value") == "Draw":
                                draw_odds = float(v.get("odd", 0))
                            elif v.get("value") == "Away":
                                away_odds = float(v.get("odd", 0))
                        break
                break

        # Если Bet365 нет, берём первый доступный
        if home_odds == 0 and odds:
            for odd in odds:
                if isinstance(odd, dict):
                    for bet in odd.get("bets", []):
                        if bet.get("name") == "Match Winner":
                            for v in bet.get("values", []):
                                if v.get("value") == "Home":
                                    home_odds = float(v.get("odd", 0))
                                elif v.get("value") == "Draw":
                                    draw_odds = float(v.get("odd", 0))
                                elif v.get("value") == "Away":
                                    away_odds = float(v.get("odd", 0))
                            break
                    if home_odds > 0:
                        break

        return {
            "fixture_id": fixture_data.get("id"),
            "date": fixture_data.get("date", "")[:10],
            "league_id": fixture.get("league", {}).get("id"),
            "league_name": fixture.get("league", {}).get("name"),
            "home_team": teams.get("home", {}).get("name"),
            "away_team": teams.get("away", {}).get("name"),
            "home_goals": home_goals,
            "away_goals": away_goals,
            "result": result,
            "B365H": home_odds,
            "B365D": draw_odds,
            "B365A": away_odds,
            "HS": home_shots,
            "AS": away_shots,
            "HST": home_shots_on_target,
            "AST": away_shots_on_target,
            "HC": home_corners,
            "AC": away_corners,
        }

    async def collect_league_data(self, league_id: int, league_name: str, sport: str,
                                   seasons: list = None) -> pd.DataFrame:
        """Собирает данные для одной лиги за несколько сезонов"""
        # Free план: только 2022-2024
        if seasons is None:
            seasons = [2022, 2023, 2024]

        all_matches = []

        for season in seasons:
            logger.info(f"📥 {league_name} ({sport}) - сезон {season}...")

            fixtures = await self.get_finished_fixtures(league_id, season)

            if isinstance(fixtures, dict) and "error" in fixtures:
                logger.warning(f"⚠️ Ошибка для {league_name} {season}: {fixtures['error']}")
                continue

            if not fixtures:
                logger.info(f"ℹ️ Нет данных для {league_name} {season}")
                continue

            logger.info(f"📊 Найдено {len(fixtures)} матчей")

            # Берём максимум 20 матчей за сезон для экономии лимита
            for fixture in fixtures[:20]:
                fixture_id = fixture.get("fixture", {}).get("id")
                if not fixture_id:
                    continue

                # Получаем статистику
                stats = await self.get_fixture_statistics(fixture_id)
                await asyncio.sleep(0.3)

                # Получаем коэффициенты
                odds = await self.get_fixture_odds(fixture_id)
                if isinstance(odds, dict) and "error" in odds:
                    odds = []
                await asyncio.sleep(0.3)

                # Извлекаем фичи
                match_data = self.extract_features(
                    fixture,
                    stats if isinstance(stats, list) else [],
                    odds if isinstance(odds, list) else []
                )
                all_matches.append(match_data)

        if all_matches:
            df = pd.DataFrame(all_matches)
            logger.info(f"✅ {league_name}: собрано {len(df)} матчей")
            return df

        return pd.DataFrame()

    async def collect_all(self):
        """Собирает данные для всех лиг"""
        logger.info("🚀 Начинаю сбор данных для хоккея и тенниса...")
        logger.info(f"📊 Лимит API: 100 запросов/день. Использовано: {self.request_count}")

        all_data = []

        # Хоккей
        logger.info("\n🏒 === ХОККЕЙ ===")
        for league_id, league_name in HOCKEY_LEAGUES.items():
            if self.request_count >= 80:
                logger.warning("⚠️ Лимит запросов, останавливаю сбор")
                break

            df = await self.collect_league_data(league_id, league_name, "hockey")
            if not df.empty:
                all_data.append(df)

            # Сохраняем промежуточные результаты
            if all_data:
                combined = pd.concat(all_data, ignore_index=True)
                combined.to_csv(self.data_dir / "hockey_matches.csv", index=False, encoding="utf-8")
                logger.info(f"💾 Сохранено {len(combined)} хоккейных матчей")

        # Теннис
        logger.info("\n🎾 === ТЕННИС ===")
        for league_id, league_name in TENNIS_LEAGUES.items():
            if self.request_count >= 80:
                logger.warning("⚠️ Лимит запросов, останавливаю сбор")
                break

            df = await self.collect_league_data(league_id, league_name, "tennis")
            if not df.empty:
                all_data.append(df)

            if all_data:
                combined = pd.concat(all_data, ignore_index=True)
                combined.to_csv(self.data_dir / "tennis_matches.csv", index=False, encoding="utf-8")
                logger.info(f"💾 Сохранено {len(combined)} теннисных матчей")

        # Итог
        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_path = self.data_dir / "hockey_tennis_all.csv"
            final_df.to_csv(final_path, index=False, encoding="utf-8")

            logger.info(f"\n🎉 Сбор завершён!")
            logger.info(f"📊 Всего собрано: {len(final_df)} матчей")
            logger.info(f"🏒 Хоккей: {len(final_df[final_df['league_name'].isin([l for l in HOCKEY_LEAGUES.values()])])}")
            logger.info(f"🎾 Теннис: {len(final_df[final_df['league_name'].isin([l for l in TENNIS_LEAGUES.values()])])}")
            logger.info(f"💾 Файл: {final_path}")
            logger.info(f"📊 API запросов использовано: {self.request_count}/100")
        else:
            logger.warning("⚠️ Не удалось собрать данные")


async def main():
    collector = HockeyTennisCollector()
    await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())
