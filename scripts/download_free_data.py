"""
Скачивание готовых бесплатных CSV-данных для хоккея и тенниса.

Источники:
- Хоккей: NHL API (бесплатный, без ключа)
- Теннис: Jeff Sackmann tennis data (GitHub)

Запуск: python scripts/download_free_data.py
"""
import asyncio
import httpx
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/historical")
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════
# ХОККЕЙ: NHL API (бесплатный)
# ═══════════════════════════════════════════════════════

async def download_nhl_data():
    """Скачивает данные NHL через официальный API"""
    logger.info("🏒 Скачиваю данные NHL...")

    all_games = []
    base_url = "https://api-web.nhle.com/v1"

    # Сезоны для скачивания
    seasons = ["20212022", "20222023", "20232024", "20242025"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for season in seasons:
            logger.info(f"📥 NHL сезон {season}...")

            # Получаем расписание сезона
            url = f"{base_url}/schedule/{season}"
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                weeks = data.get("gameWeeks", [])
                for week in weeks:
                    for game in week.get("games", []):
                        game_id = game.get("id")
                        game_type = game.get("gameType")

                        # Только regular season (R) и playoff (P)
                        if game_type not in ["R", "P"]:
                            continue

                        home_team = game.get("homeTeam", {})
                        away_team = game.get("awayTeam", {})

                        home_score = home_team.get("score", 0)
                        away_score = away_team.get("score", 0)

                        if home_score is None or away_score is None:
                            continue

                        # Определяем результат
                        if home_score > away_score:
                            result = "H"
                        elif home_score < away_score:
                            result = "A"
                        else:
                            result = "D"  # В NHL нет ничьих, но на всякий случай

                        game_date = game.get("date", "")

                        all_games.append({
                            "fixture_id": f"nhl_{game_id}",
                            "date": game_date,
                            "league_name": "NHL",
                            "home_team": home_team.get("name", ""),
                            "away_team": away_team.get("name", ""),
                            "home_goals": home_score,
                            "away_goals": away_score,
                            "result": result,
                            "B365H": 0,  # NHL API не даёт коэффициенты
                            "B365D": 0,
                            "B365A": 0,
                            "HS": 0,
                            "AS": 0,
                            "HST": 0,
                            "AST": 0,
                            "HC": 0,
                            "AC": 0,
                        })

                logger.info(f"  ✅ Сезон {season}: {len([g for g in all_games if season in g.get('fixture_id', '')])} игр")
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"  ⚠️ Ошибка сезона {season}: {e}")

    if all_games:
        df = pd.DataFrame(all_games)
        output_path = DATA_DIR / "nhl_matches.csv"
        df.to_csv(output_path, index=False, encoding="utf-8")
        logger.info(f"💾 NHL: {len(df)} матчей сохранено в {output_path}")
        return df

    return pd.DataFrame()


# ═══════════════════════════════════════════════════════
# ТЕННИС: Jeff Sackmann data (GitHub)
# ═══════════════════════════════════════════════════════

async def download_tennis_data():
    """Скачивает данные тенниса с GitHub Jeff Sackmann"""
    logger.info("🎾 Скачиваю данные тенниса...")

    # Jeff Sackmann хранит данные по годам
    base_url = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"

    years = range(2015, 2026)
    all_matches = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for year in years:
            url = f"{base_url}/atp_matches_{year}.csv"
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    # Сохраняем временно и читаем
                    temp_path = DATA_DIR / f"tennis_temp_{year}.csv"
                    temp_path.write_bytes(response.content)

                    df = pd.read_csv(temp_path, encoding="utf-8-sig")
                    temp_path.unlink()

                    if not df.empty:
                        # Преобразуем в наш формат
                        processed = pd.DataFrame({
                            "fixture_id": [f"tennis_{row.get('match_num', i)}_{year}" for i, row in df.iterrows()],
                            "date": df.get("tourney_date", ""),
                            "league_name": df.get("tourney_name", "ATP"),
                            "home_team": df.get("winner_name", ""),
                            "away_team": df.get("loser_name", ""),
                            "home_goals": df.get("w_ace", 0).fillna(0).astype(int),
                            "away_goals": df.get("l_ace", 0).fillna(0).astype(int),
                            "result": "H",  # Winner is always "home" in this dataset
                            "B365H": 0,
                            "B365D": 0,  # Tennis has no draw
                            "B365A": 0,
                            "HS": df.get("w_svpt", 0).fillna(0).astype(int),
                            "AS": df.get("l_svpt", 0).fillna(0).astype(int),
                            "HST": df.get("w_1stIn", 0).fillna(0).astype(int),
                            "AST": df.get("l_1stIn", 0).fillna(0).astype(int),
                            "HC": 0,
                            "AC": 0,
                        })
                        all_matches.append(processed)
                        logger.info(f"  ✅ {year}: {len(df)} матчей")

                await asyncio.sleep(0.3)

            except Exception as e:
                logger.warning(f"  ⚠️ Ошибка {year}: {e}")

    if all_matches:
        df = pd.concat(all_matches, ignore_index=True)
        output_path = DATA_DIR / "tennis_matches.csv"
        df.to_csv(output_path, index=False, encoding="utf-8")
        logger.info(f"💾 Теннис: {len(df)} матчей сохранено в {output_path}")
        return df

    return pd.DataFrame()


# ═══════════════════════════════════════════════════════
# ОСНОВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════

async def main():
    logger.info("🚀 Скачивание бесплатных данных...")

    # Скачиваем хоккей
    nhl_df = await download_nhl_data()

    # Скачиваем теннис
    tennis_df = await download_tennis_data()

    # Итог
    logger.info("\n📊 ИТОГ:")
    logger.info(f"  🏒 NHL: {len(nhl_df)} матчей")
    logger.info(f"  🎾 Теннис: {len(tennis_df)} матчей")

    if not nhl_df.empty or not tennis_df.empty:
        logger.info("\n✅ Данные готовы для переобучения модели!")
        logger.info("   Следующий шаг: python scripts/train_ensemble_model.py")
    else:
        logger.warning("⚠️ Не удалось скачать данные")


if __name__ == "__main__":
    asyncio.run(main())
