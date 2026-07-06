from pathlib import Path

web_file = Path("web/main.py")
content = web_file.read_text(encoding="utf-8")

# 1. Заменяем "date" на "match_date" в SELECT и ORDER BY
content = content.replace(
    "SELECT fixture_id, home_team, away_team, date,",
    "SELECT fixture_id, home_team, away_team, match_date,"
)
content = content.replace(
    "ORDER BY date DESC",
    "ORDER BY match_date DESC"
)

# 2. Исправляем маппинг в словаре pred (row["date"] → row["match_date"])
content = content.replace(
    '"date": str(row["date"])',
    '"date": str(row["match_date"])'
)

web_file.write_text(content, encoding="utf-8")
print("✅ web/main.py исправлен: date → match_date")
