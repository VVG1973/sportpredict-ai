"""
Обработка CSV файлов с xG данными из Understat
Объединяет все файлы в единый датасет
"""
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


def process_understat_csv(file_path: Path, league: str, season: int) -> List[Dict]:
    """Обрабатывает один CSV файл с Understat"""
    matches = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    match = {
                        "fixture_id": f"understat_{row.get('id', '')}",
                        "league": league,
                        "season": season,
                        "date": row.get("date", ""),
                        "home_team": row.get("home_team", ""),
                        "away_team": row.get("away_team", ""),
                        "home_goals": int(row.get("home_goals", 0) or 0),
                        "away_goals": int(row.get("away_goals", 0) or 0),
                        "home_xg": float(row.get("home_xg", 0) or 0),
                        "away_xg": float(row.get("away_xg", 0) or 0),
                        "result": "H" if int(row.get("home_goals", 0) or 0) > int(row.get("away_goals", 0) or 0)
                                  else "A" if int(row.get("home_goals", 0) or 0) < int(row.get("away_goals", 0) or 0)
                                  else "D",
                    }
                    matches.append(match)
                except (ValueError, KeyError) as e:
                    logger.debug(f"Пропуск строки: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"❌ Ошибка чтения {file_path}: {e}")
    
    return matches


def main():
    print("=" * 60)
    print("🔧 ОБРАБОТКА CSV ФАЙЛОВ С UNDERSTAT")
    print("=" * 60)
    print()
    
    xg_dir = Path("data/historical/xg")
    if not xg_dir.exists():
        print(f"❌ Папка не найдена: {xg_dir}")
        print("💡 Создайте папку и скачайте CSV файлы с Understat")
        return
    
    # Ищем все CSV файлы
    csv_files = list(xg_dir.glob("*.csv"))
    print(f"📂 Найдено {len(csv_files)} CSV файлов")
    
    if not csv_files:
        print("❌ CSV файлы не найдены")
        print("💡 Скачайте файлы с Understat (см. инструкцию выше)")
        return
    
    all_matches = []
    
    for csv_file in csv_files:
        # Извлекаем лигу и сезон из имени файла
        # Формат: EPL_2024.csv, La_liga_2023.csv, и т.д.
        parts = csv_file.stem.split("_")
        if len(parts) >= 2:
            league = parts[0]
            season = int(parts[1])
            
            matches = process_understat_csv(csv_file, league, season)
            all_matches.extend(matches)
            
            print(f"   ✅ {csv_file.name}: {len(matches)} матчей")
    
    if not all_matches:
        print("\n❌ Не удалось обработать ни одного файла")
        return
    
    # Сохраняем объединённый датасет
    output_path = xg_dir / "xg_matches.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_matches, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Сохранено {len(all_matches)} матчей с xG")
    print(f"   JSON: {output_path}")
    
    # Статистика
    print("\n" + "=" * 60)
    print("📈 СТАТИСТИКА ПО ЛИГАМ:")
    print("=" * 60)
    
    leagues = set(m["league"] for m in all_matches)
    for league in sorted(leagues):
        count = sum(1 for m in all_matches if m["league"] == league)
        print(f"  {league:15s} : {count:4d} матчей")
    
    print(f"\n  {'ВСЕГО':15s} : {len(all_matches):4d} матчей")
    
    # Средний xG
    avg_home_xg = sum(m["home_xg"] for m in all_matches) / len(all_matches)
    avg_away_xg = sum(m["away_xg"] for m in all_matches) / len(all_matches)
    
    print("\n" + "=" * 60)
    print("📊 СРЕДНИЙ XG:")
    print("=" * 60)
    print(f"   Хозяева: {avg_home_xg:.3f}")
    print(f"   Гости: {avg_away_xg:.3f}")
    print(f"   Разница: {avg_home_xg - avg_away_xg:.3f}")
    
    print("\n✅ Готово к следующему шагу!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
