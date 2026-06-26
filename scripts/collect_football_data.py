"""
Загрузчик данных с football-data.co.uk
Надёжный источник с 20+ признаками для ML
"""
import csv
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import httpx

logger = logging.getLogger(__name__)

# Лиги на football-data.co.uk
LEAGUES = {
    "E0": "Английская Премьер-лига",
    "E1": "Английский Чемпионшип",
    "SP1": "Ла Лига",
    "D1": "Бундеслига",
    "I1": "Серия А",
    "F1": "Лига 1",
    "N1": "Эредивизи",
    "P1": "Примейра Лига",
    "B1": "Жюпилер Лига",
    "T1": "Суперлига Турции",
}


def safe_float(value) -> float:
    try:
        return float(value) if value and value.strip() != "" else 0.0
    except (ValueError, TypeError, AttributeError):
        return 0.0


def safe_int(value) -> int:
    try:
        return int(value) if value and value.strip() != "" else 0
    except (ValueError, TypeError, AttributeError):
        return 0


def download_league_season(league_code: str, season: int) -> List[Dict]:
    """Скачивает CSV файл лиги за сезон"""
    # Формат сезона: 2324 = 2023/2024
    season_str = f"{str(season)[2:]}{str(season+1)[2:]}"
    url = f"https://www.football-data.co.uk/mmz4281/{season_str}/{league_code}.csv"
    
    logger.info(f"📊 Скачивание: {league_code} ({LEAGUES.get(league_code, league_code)}) {season}/{season+1}")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Парсим CSV
            csv_text = response.text
            lines = csv_text.split("\n")
            
            if len(lines) < 2:
                logger.warning(f"   ⚠️ Пустой CSV для {league_code} {season}")
                return []
            
            # Читаем CSV
            reader = csv.DictReader(lines)
            matches = []
            
            for row in reader:
                try:
                    match = {
                        "fixture_id": f"fd_{row.get('Div', '')}_{row.get('Date', '')}_{row.get('HomeTeam', '')}_{row.get('AwayTeam', '')}",
                        "league": league_code,
                        "league_ru": LEAGUES.get(league_code, league_code),
                        "season": season,
                        "date": row.get("Date", ""),
                        "home_team": row.get("HomeTeam", ""),
                        "away_team": row.get("AwayTeam", ""),
                        "home_goals": safe_int(row.get("FTHG", 0)),
                        "away_goals": safe_int(row.get("FTAG", 0)),
                        "result": row.get("FTR", ""),  # H/D/A
                        # Коэффициенты Bet365
                        "b365_home": safe_float(row.get("B365H", 0)),
                        "b365_draw": safe_float(row.get("B365D", 0)),
                        "b365_away": safe_float(row.get("B365A", 0)),
                        # Коэффициенты Bet&Win
                        "bw_home": safe_float(row.get("BWH", 0)),
                        "bw_draw": safe_float(row.get("BWD", 0)),
                        "bw_away": safe_float(row.get("BWA", 0)),
                        # Коэффициенты Interwetten
                        "iw_home": safe_float(row.get("IWH", 0)),
                        "iw_draw": safe_float(row.get("IWD", 0)),
                        "iw_away": safe_float(row.get("IWA", 0)),
                        # Коэффициенты Pinnacle
                        "ps_home": safe_float(row.get("PSH", 0)),
                        "ps_draw": safe_float(row.get("PSD", 0)),
                        "ps_away": safe_float(row.get("PSA", 0)),
                        # Коэффициенты William Hill
                        "wh_home": safe_float(row.get("WHH", 0)),
                        "wh_draw": safe_float(row.get("WHD", 0)),
                        "wh_away": safe_float(row.get("WHA", 0)),
                        # Удары
                        "home_shots": safe_int(row.get("HS", 0)),
                        "away_shots": safe_int(row.get("AS", 0)),
                        "home_shots_on_target": safe_int(row.get("HST", 0)),
                        "away_shots_on_target": safe_int(row.get("AST", 0)),
                        # Фолы
                        "home_fouls": safe_int(row.get("HF", 0)),
                        "away_fouls": safe_int(row.get("AF", 0)),
                        # Угловые
                        "home_corners": safe_int(row.get("HC", 0)),
                        "away_corners": safe_int(row.get("AC", 0)),
                        # Карточки
                        "home_yellow": safe_int(row.get("HY", 0)),
                        "away_yellow": safe_int(row.get("AY", 0)),
                        "home_red": safe_int(row.get("HR", 0)),
                        "away_red": safe_int(row.get("AR", 0)),
                    }
                    matches.append(match)
                except Exception as e:
                    logger.debug(f"Пропуск строки: {e}")
                    continue
            
            logger.info(f"   ✅ Получено {len(matches)} матчей")
            return matches
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"   ⚠️ CSV не найден (404) для {league_code} {season}")
        else:
            logger.error(f"❌ HTTP ошибка {league_code} {season}: {e}")
        return []
    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP ошибка {league_code} {season}: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Ошибка {league_code} {season}: {e}")
        return []


def collect_all(seasons: list = None) -> List[Dict]:
    """Собирает все лиги за указанные сезоны"""
    if seasons is None:
        current_year = datetime.now().year
        seasons = [current_year - 1, current_year - 2, current_year - 3]
    
    logger.info(f"🚀 Сбор данных football-data.co.uk для сезонов: {seasons}")
    logger.info(f"📊 Лиг: {len(LEAGUES)}")
    
    all_matches = []
    
    for league_code in LEAGUES.keys():
        for season in seasons:
            matches = download_league_season(league_code, season)
            all_matches.extend(matches)
            time.sleep(1)  # Вежливая задержка
    
    return all_matches


def main():
    print("=" * 60)
    print("📊 СБОР ДАННЫХ С FOOTBALL-DATA.CO.UK")
    print("=" * 60)
    print()
    print("⏳ Процесс займёт 2-5 минут")
    print("🌐 Источник: football-data.co.uk")
    print("📈 Признаки: 35+ (коэффициенты, удары, угловые, карточки)")
    print("🎯 Ожидаемая точность ML: 52-55% (вместо 45%)")
    print()
    
    # Собираем последние 5 сезонов
    matches = collect_all(seasons=[2024, 2023, 2022, 2021, 2020])
    
    if not matches:
        print("\n❌ Сбор данных не удался")
        return
    
    # Сохраняем
    data_dir = Path("data/historical")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = data_dir / "football_data_matches.csv"
    json_path = data_dir / "football_data_matches.json"
    
    # CSV
    keys = matches[0].keys()
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(matches)
    
    # JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Сохранено {len(matches)} матчей:")
    print(f"   CSV: {csv_path}")
    print(f"   JSON: {json_path}")
    
    # Статистика
    print("\n" + "=" * 60)
    print("📈 СТАТИСТИКА ПО ЛИГАМ:")
    print("=" * 60)
    for league_code in LEAGUES.keys():
        count = sum(1 for m in matches if m["league"] == league_code)
        if count > 0:
            print(f"  {LEAGUES.get(league_code, league_code):25s} : {count:4d} матчей")
    
    print(f"\n  {'ВСЕГО':25s} : {len(matches):4d} матчей")
    
    # Первые 3 матча
    print("\n" + "=" * 60)
    print("📋 ПЕРВЫЕ 3 МАТЧА:")
    print("=" * 60)
    for m in matches[:3]:
        print(f"{m['league']} | {m['home_team']} vs {m['away_team']}")
        print(f"   Счёт: {m['home_goals']}:{m['away_goals']} | Результат: {m['result']}")
        print(f"   B365: {m['b365_home']:.2f}/{m['b365_draw']:.2f}/{m['b365_away']:.2f}")
        print(f"   Удары: {m['home_shots']} vs {m['away_shots']} | Угловые: {m['home_corners']} vs {m['away_corners']}")
        print()
    
    print("✅ Сбор завершён!")
    print("🎯 Следующий шаг: переобучение ML модели с новыми признаками")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    main()
