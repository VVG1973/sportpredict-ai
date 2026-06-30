import json
from pathlib import Path

path = Path("data/historical/football_data_matches.json")
if not path.exists():
    print(f"❌ Файл не найден: {path}")
    exit(1)

with open(path, encoding="utf-8") as f:
    matches = json.load(f)

print(f"✅ Всего матчей: {len(matches)}")
print(f"📅 Первый матч: {matches[0].get('date', 'N/A')} - {matches[0].get('home_team', 'N/A')} vs {matches[0].get('away_team', 'N/A')}")
print(f"📅 Последний матч: {matches[-1].get('date', 'N/A')} - {matches[-1].get('home_team', 'N/A')} vs {matches[-1].get('away_team', 'N/A')}")
print(f"📊 Признаков в матче: {len(matches[-1].keys())}")

# Проверяем наличие ключевых признаков
required = ["b365_home", "home_shots_on_target", "home_corners", "home_fouls"]
print("\n🔍 Проверка признаков:")
for key in required:
    value = matches[-1].get(key, "ОТСУТСТВУЕТ")
    print(f"   {key}: {value}")
