"""
Сортируем матчи по дате (от старых к новым)
"""
import json
from pathlib import Path
from datetime import datetime

path = Path("data/historical/football_data_matches.json")
with open(path, encoding="utf-8") as f:
    matches = json.load(f)

print(f"📚 Всего матчей: {len(matches)}")

def parse_date(date_str):
    """Парсит дату в формате DD/MM/YYYY"""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except (ValueError, TypeError):
        return datetime.min

# Сортируем по дате
matches_sorted = sorted(matches, key=lambda m: parse_date(m.get("date", "")))

# Сохраняем
with open(path, "w", encoding="utf-8") as f:
    json.dump(matches_sorted, f, ensure_ascii=False, indent=2)

print(f"✅ Данные отсортированы")
print(f"📅 Первый матч: {matches_sorted[0].get('date')} - {matches_sorted[0].get('home_team')} vs {matches_sorted[0].get('away_team')}")
print(f"📅 Последний матч: {matches_sorted[-1].get('date')} - {matches_sorted[-1].get('home_team')} vs {matches_sorted[-1].get('away_team')}")
