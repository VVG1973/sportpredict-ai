"""
Генерация синтетических xG из имеющейся статистики
Использует удары в створ, угловые и фолы как прокси для xG
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_synthetic_xg(home_shots_on_target, away_shots_on_target,
                           home_corners, away_corners,
                           home_fouls, away_fouls):
    """
    Приближённая формула xG на основе доступной статистики.
    Коэффициенты подобраны эмпирически.
    """
    home_xg = 0.10 * home_shots_on_target + 0.03 * home_corners + 0.005 * home_fouls
    away_xg = 0.10 * away_shots_on_target + 0.03 * away_corners + 0.005 * away_fouls
    return home_xg, away_xg


def main():
    print("=" * 60)
    print("🔧 ГЕНЕРАЦИЯ СИНТЕТИЧЕСКИХ XG")
    print("=" * 60)
    print()
    
    input_path = Path("data/historical/football_data_matches.json")
    if not input_path.exists():
        print(f"❌ Файл не найден: {input_path}")
        return
    
    with open(input_path, "r", encoding="utf-8") as f:
        matches = json.load(f)
    
    print(f"📚 Загружено {len(matches)} матчей")
    
    for match in matches:
        home_sot = int(match.get("home_shots_on_target", 0) or 0)
        away_sot = int(match.get("away_shots_on_target", 0) or 0)
        home_corners = int(match.get("home_corners", 0) or 0)
        away_corners = int(match.get("away_corners", 0) or 0)
        home_fouls = int(match.get("home_fouls", 0) or 0)
        away_fouls = int(match.get("away_fouls", 0) or 0)
        
        home_xg, away_xg = calculate_synthetic_xg(
            home_sot, away_sot, home_corners, away_corners, home_fouls, away_fouls
        )
        
        match["home_xg"] = round(home_xg, 3)
        match["away_xg"] = round(away_xg, 3)
        match["xg_diff"] = round(home_xg - away_xg, 3)
        
        home_shots = int(match.get("home_shots", 1) or 1)
        away_shots = int(match.get("away_shots", 1) or 1)
        match["home_sot_ratio"] = round(home_sot / max(home_shots, 1), 3)
        match["away_sot_ratio"] = round(away_sot / max(away_shots, 1), 3)
        match["home_dominance"] = round(home_xg - away_xg + home_corners - away_corners, 3)
    
    output_path = Path("data/historical/football_data_matches_with_xg.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Сохранено {len(matches)} матчей с синтетическими xG")
    print(f"   JSON: {output_path}")
    
    avg_home_xg = sum(m["home_xg"] for m in matches) / len(matches)
    avg_away_xg = sum(m["away_xg"] for m in matches) / len(matches)
    
    print()
    print("=" * 60)
    print("📊 СТАТИСТИКА:")
    print("=" * 60)
    print(f"   Средний xG хозяев: {avg_home_xg:.3f}")
    print(f"   Средний xG гостей: {avg_away_xg:.3f}")
    print(f"   Разница: {avg_home_xg - avg_away_xg:.3f}")
    print()
    print("✅ Готово к обучению модели!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
