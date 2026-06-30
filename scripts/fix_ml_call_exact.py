"""
Точечное исправление вызова ml_model.predict() в run_pipeline
"""
import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Ищем неправильный вызов с именованными аргументами
wrong_pattern = r'ml_result\s*=\s*ml_model\.predict\(\s*home_team=home_team,\s*away_team=away_team,\s*match_date=match_date,\s*historical_df=historical_df\s*\)'

if re.search(wrong_pattern, content, re.DOTALL):
    print("⚠️ Найден НЕПРАВИЛЬНЫЙ вызов ml_model.predict() с именованными аргументами!")
    
    # Правильный вызов с словарем
    correct_call = '''ml_result = ml_model.predict({
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "historical_df": historical_df
        })'''
    
    content = re.sub(wrong_pattern, correct_call, content, flags=re.DOTALL)
    path.write_text(content, encoding="utf-8")
    print("✅ Вызов ml_model.predict() исправлен (передается словарь)")
    print("💾 main.py сохранен!")
else:
    # Попробуем найти любой вызов ml_model.predict
    matches = list(re.finditer(r'ml_model\.predict\([^)]+\)', content, re.DOTALL))
    if matches:
        print(f"⚠️ Найдено {len(matches)} вызовов ml_model.predict:")
        for i, match in enumerate(matches, 1):
            snippet = match.group(0)[:200]
            print(f"   {i}. {snippet}...")
    else:
        print("⚠️ Вызов ml_model.predict не найден в main.py")
