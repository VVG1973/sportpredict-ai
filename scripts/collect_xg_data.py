"""
Надёжный загрузчик xG данных с Understat.com
Работает на httpx (без aiohttp, без understat, без pandas)
Совместим с Python 3.14+
"""
import json
import csv
import logging
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import httpx

logger = logging.getLogger(__name__)

LEAGUES = ["EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1", "RFPL"]

LEAGUE_NAMES_RU = {
    "EPL": "Английская Премьер-лига",
    "La_liga": "Ла Лига",
    "Bundesliga": "Бундеслига",
    "Serie_A": "Серия А",
    "Ligue_1": "Лига 1",
    "RFPL": "РПЛ",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def safe_int(value) -> int:
    try:
        return int(value) if value not in (None, "") else 0
    except (ValueError, TypeError):
        return 0


def safe_float(value) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except (ValueError, TypeError):
        return 0.0


def extract_json_variable(html: str, var_name: str) -> list:
    """Извлекает JSON из JavaScript переменной Understat"""
    # Understat хранит данные как: var datesData = JSON.parse('...')
    # Внутри строки escape-последовательности: \x27 (одинарная кавычка) и т.д.
    patterns = [
        rf"var\s+{var_name}\s*=\s*JSON\.parse\('(.+?)'\)",
        rf"{var_name}\s*=\s*JSON\.parse\('(.+?)'\)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                # Декодируем escape-последовательности
                decoded = bytes(json_str, "utf-8").decode("unicode_escape")
                return json.loads(decoded)
            except Exception as e:
                logger.error(f"❌ Ошибка декодирования {var_name}: {e}")
                continue
    
    return []


def collect_league_season(league: str, season: int) -> List[Dict]:
    """Собирает матчи одной лиги за один сезон"""
    url = f"https://understat.com/league/{league}/{season}"
    logger.info(f"📊 Запрос: {league} {season}/{season+1}")
    
    try:
        with httpx.Client(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            
            html = response.text
            logger.info(f"   HTML получен: {len(html)} символов")
            
            # Проверяем, есть ли datesData в HTML
            if "datesData" not in html:
                logger.warning(f"   ⚠️ datesData НЕ найдена в HTML (сайт может блокировать)")
                return []
            
            matches = extract_json_variable(html, "datesData")
            
            if not matches:
                logger.warning(f"   ⚠️ Не удалось извлечь datesData")
                return []
            
            logger.info(f"   ✅ Извлечено {len(matches)} записей")
            
            # Преобразуем в нужный формат
            results = []
            for m in matches:
                try:
                    if not isinstance(m, dict):
                        continue
                    
                    # Проверяем, что это завершённый матч
                    is_result = m.get("isResult", False)
                    if not is_result:
                        continue
                    
                    row = {
                        "fixture_id": f"understat_{m.get('id', '')}",
                        "league": league,
                        "league_ru": LEAGUE_NAMES_RU.get(league, league),
                        "season": season,
                        "date": m.get("datetime", ""),
                        "home_team": m.get("h", {}).get("title", "") if isinstance(m.get("h"), dict) else "",
                        "away_team": m.get("a", {}).get("title", "") if isinstance(m.get("a"), dict) else "",
                        "home_goals": safe_int(m.get("goals", {}).get("h", 0)),
                        "away_goals": safe_int(m.get("goals", {}).get("a", 0)),
                        "home_xg": safe_float(m.get("xG", {}).get("h", 0)),
                        "away_xg": safe_float(m.get("xG", {}).get("a", 0)),
                        "forecast_home": safe_float(m.get("forecast", {}).get("w", 0)),
                        "forecast_draw": safe_float(m.get("forecast", {}).get("d", 0)),
                        "forecast_away": safe_float(m.get("forecast", {}).get("l", 0)),
                        "result": m.get("result", ""),
                        "isResult": True,
                    }
                    
                    if row["home_team"] and row["away_team"]:
                        results.append(row)
                except Exception as e:
                    logger.debug(f"Пропуск матча: {e}")
                    continue
            
            logger.info(f"   🏆 Завершённых матчей: {len(results)}")
            return results
    
    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP ошибка {league} {season}: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Ошибка {league} {season}: {e}")
        return []


def collect_all(seasons: list = None) -> List[Dict]:
    """Собирает все лиги за указанные сезоны"""
    if seasons is None:
        current_year = datetime.now().year
        seasons = [current_year - 1, current_year - 2, current_year - 3]
    
    logger.info(f"🚀 Сбор данных для сезонов: {seasons}")
    logger.info(f"📊 Лиг: {len(LEAGUES)} ({', '.join(LEAGUES)})")
    
    all_matches = []
    
    for league in LEAGUES:
        for season in seasons:
            matches = collect_league_season(league, season)
            all_matches.extend(matches)
            time.sleep(2)  # Вежливая задержка
    
    return all_matches


def main():
    print("=" * 60)
    print("📊 СБОР XG ДАННЫХ С UNDERSTAT.COM (HTTPX)")
    print("=" * 60)
    print()
    print("⏳ Процесс займёт 3-7 минут")
    print("🌐 Источник: understat.com (через datesData)")
    print("🔧 НЕ требует библиотеку understat (работает на httpx)")
    print()
    
    # Собираем последние 5 сезонов
    matches = collect_all(seasons=[2024, 2023, 2022, 2021, 2020])
    
    if not matches:
        print("\n❌ Сбор данных не удался")
        return
    
    # Сохраняем в CSV и JSON (без pandas)
    data_dir = Path("data/historical/xg")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = data_dir / "all_matches_xg.csv"
    json_path = data_dir / "all_matches_xg.json"
    
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
    
    # Статистика по лигам
    print("\n" + "=" * 60)
    print("📈 СТАТИСТИКА ПО ЛИГАМ:")
    print("=" * 60)
    for league in LEAGUES:
        count = sum(1 for m in matches if m["league"] == league)
        print(f"  {LEAGUE_NAMES_RU.get(league, league):25s} : {count:4d} матчей")
    
    print(f"\n  {'ВСЕГО':25s} : {len(matches):4d} матчей")
    
    # Первые 5 матчей
    print("\n" + "=" * 60)
    print("📋 ПЕРВЫЕ 3 МАТЧА:")
    print("=" * 60)
    for m in matches[:3]:
        print(f"{m['league']} | {m['home_team']} vs {m['away_team']}")
        print(f"   Счёт: {m['home_goals']}:{m['away_goals']} | xG: {m['home_xg']:.2f} vs {m['away_xg']:.2f}")
        print()
    
    print("✅ Сбор завершён!")
    print("🎯 Следующий шаг: переобучение ML модели с xG признаками")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    main()
