"""
Исправляет вызов ml_model.predict() в run_pipeline
"""
import re
from pathlib import Path

main_path = Path("main.py")
content = main_path.read_text(encoding="utf-8")

# Ищем неправильный вызов
wrong_pattern = r'ml_result\s*=\s*ml_model\.predict\(\s*home_team=home_team,\s*away_team=away_team,\s*match_date=match_date,\s*historical_df=historical_df\s*\)'

if re.search(wrong_pattern, content, re.DOTALL):
    # Правильный вызов с словарем
    correct_call = '''ml_result = ml_model.predict({
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "historical_df": historical_df
        })'''
    
    content = re.sub(wrong_pattern, correct_call, content, flags=re.DOTALL)
    main_path.write_text(content, encoding="utf-8")
    print("✅ Вызов ml_model.predict() исправлен!")
    print("   Теперь данные передаются через словарь (правильно)")
else:
    print("⚠️ Паттерн не найден. Возможно, уже исправлено или формат отличается")
    print("💡 Попробуем запасной вариант...")
    
    # Запасной вариант: ищем любую строку с ml_model.predict
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'ml_model.predict' in line and 'home_team' in line:
            print(f"   Найдено на строке {i+1}: {line.strip()}")
