"""
Объединение xG данных с коэффициентами букмекеров
Создаёт датасет для обучения честной модели с xG
"""
import json
import logging
from pathlib import Path
from typing import Dict, List
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def normalize_team_name(name: str) -> str:
    """Нормализует название команды для сопоставления"""
    name = name.lower().strip()
    replacements = {
        "manchester united": "man united",
        "manchester city": "man city",
        "tottenham hotspur": "tottenham",
        "newcastle united": "newcastle",
        "west ham united": "west ham",
        "atletico madrid": "atlético madrid",
        "bayern munich": "bayern münchen",
        "borussia dortmund": "dortmund",
        "inter milan": "inter",
        "ac milan": "milan",
        "paris saint-germain": "psg",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name


def similarity(a: str, b: str) -> float:
    """Вычисляет сходство двух строк"""
    return SequenceMatcher(None, a, b).ratio()


def find_best_match(team_name: str, available_teams: List[str]) -> str:
    """Находит наиболее похожее название команды"""
    normalized = normalize_team_name(team_name)
    best_match = None
    best_score = 0
    
    for available in available_teams:
        norm_available = normalize_team_name(available)
        score = similarity(normalized, norm_available)
        
        if score > best_score:
            best_score = score
            best_match = available
    
    return best_match if best_score > 0.7 else None


def load_xg_data(xg_path: str = "data/historical/xg/xg_matches.json") -> List[Dict]:
    """Загружает xG данные"""
    if not Path(xg_path).exists():
        logger.error(f"❌ Файл не найден: {xg_path}")
        return []
    
    with open(xg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_matches_data(matches_path: str = "data/historical/football_data_matches.json") -> List[Dict]:
    """Загружает данные матчей с коэффициентами"""
    if not Path(matches_path).exists():
        logger.error(f"❌ Файл не найден: {matches_path}")
        return []
    
    with open(matches_path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_data(xg_matches: List[Dict], matches: List[Dict]) -> List[Dict]:
    """Объединяет xG данные с коэффициентами"""
    logger.info(f"🔧 Объединение {len(xg_matches)} xG матчей с {len(matches)} матчами с коэф.")
    
    # Создаём словарь xG данных для быстрого поиска
    xg_dict = {}
    for m in xg_matches:
        key = f"{m['league']}_{m['season']}_{normalize_team_name(m['home_team'])}_{normalize_team_name(m['away_team'])}"
        xg_dict[key] = m
    
    # Объединяем
    merged = []
    matched_count = 0
    
    for match in matches:
        league = match.get("league", "")
        season = match.get("season", 0)
        home = normalize_team_name(match.get("home_team", ""))
        away = normalize_team_name(match.get("away_team", ""))
        
        key = f"{league}_{season}_{home}_{away}"
        
        if key in xg_dict:
            xg_data = xg_dict[key]
            
            # Добавляем xG признаки
            match["home_xg"] = xg_data.get("home_xg", 0.0)
            match["away_xg"] = xg_data.get("away_xg", 0.0)
            match["xg_diff"] = match["home_xg"] - match["away_xg"]
            
            merged.append(match)
            matched_count += 1
    
    logger.info(f"✅ Сопоставлено {matched_count} из {len(matches)} матчей")
    logger.info(f"⚠️ Не найдено xG для {len(matches) - matched_count} матчей")
    
    return merged


def main():
    print("=" * 60)
    print("🔧 ОБЪЕДИНЕНИЕ XG ДАННЫХ С КОЭФФИЦИЕНТАМИ")
    print("=" * 60)
    print()
    
    xg_matches = load_xg_data()
    matches = load_matches_data()
    
    if not xg_matches or not matches:
        print("❌ Не удалось загрузить данные")
        return
    
    merged = merge_data(xg_matches, matches)
    
    if not merged:
        print("❌ Не удалось объединить данные")
        return
    
    # Сохраняем
    output_path = Path("data/historical/merged_matches_xg.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Сохранено {len(merged)} матчей с xG + коэффициентами")
    print(f"   JSON: {output_path}")
    
    # Статистика
    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА:")
    print("=" * 60)
    print(f"   Матчей с xG: {len(merged)}")
    print(f"   Признаков: 40 (коэф.) + 3 (xG) = 43")
    print()
    print("✅ Готово к обучению модели!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
