"""
Конвертация WTA теннисных данных в формат модели
"""
import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/historical")


def convert_wta_to_model_format():
    """Конвертирует WTA данные в формат, понятный модели"""
    input_file = DATA_DIR / "wta_matches.csv"
    output_file = DATA_DIR / "tennis_matches.csv"

    if not input_file.exists():
        logger.error(f"❌ Файл не найден: {input_file}")
        return

    logger.info(f"📥 Загружаю WTA данные: {input_file}")
    df = pd.read_csv(input_file, low_memory=False)
    logger.info(f"📊 Загружено {len(df)} матчей")

    # Конвертируем в формат модели
    matches = []

    for idx, row in df.iterrows():
        try:
            # Дата
            date_str = str(row.get("Date", ""))
            if len(date_str) >= 10:
                date_str = date_str[:10]
            else:
                continue

            # Игроки
            player1 = str(row.get("Player_1", ""))
            player2 = str(row.get("Player_2", ""))
            winner = str(row.get("Winner", ""))

            if not player1 or not player2 or not winner:
                continue

            # Рейтинги
            rank1 = int(row.get("Rank_1", 0) or 0)
            rank2 = int(row.get("Rank_2", 0) or 0)

            # Коэффициенты
            odd1 = float(row.get("Odd_1", 0) or 0)
            odd2 = float(row.get("Odd_2", 0) or 0)

            # Определяем результат
            if winner == player1:
                result = "H"
            elif winner == player2:
                result = "A"
            else:
                result = "H"  # По умолчанию

            # Турнир и поверхность
            tournament = str(row.get("Tournament", ""))
            surface = str(row.get("Surface", ""))

            matches.append({
                "fixture_id": f"wta_{idx}",
                "date": date_str,
                "league_name": f"{tournament} ({surface})",
                "home_team": player1,
                "away_team": player2,
                "home_goals": 0,  # Нет данных по ace
                "away_goals": 0,
                "result": result,
                "B365H": odd1,
                "B365D": 0,  # В теннисе нет ничьих
                "B365A": odd2,
                "HS": 0,  # Подачи (нет в данных)
                "AS": 0,
                "HST": 0,
                "AST": 0,
                "HC": 0,
                "AC": 0,
                "sport": "🎾 Теннис",
                "is_real": True,
                "rank1": rank1,
                "rank2": rank2,
            })
        except Exception as e:
            continue

    if matches:
        result_df = pd.DataFrame(matches)
        result_df.to_csv(output_file, index=False, encoding="utf-8")
        logger.info(f"✅ Сохранено {len(result_df)} теннисных матчей в {output_file}")
    else:
        logger.error("❌ Не удалось конвертировать данные")


if __name__ == "__main__":
    convert_wta_to_model_format()
