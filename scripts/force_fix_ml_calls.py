"""
Принудительная замена всех вызовов ml_model.predict в main.py
"""
import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")
original_content = content

# Ищем все вызовы ml_model.predict с kwargs
pattern = r'ml_model\.predict\(\s*home_team\s*=\s*home_team\s*,\s*away_team\s*=\s*away_team\s*,\s*match_date\s*=\s*match_date\s*,\s*historical_df\s*=\s*historical_df\s*\)'

matches = list(re.finditer(pattern, content, re.DOTALL))
print(f"🔍 Найдено {len(matches)} вызовов ml_model.predict с kwargs")

if matches:
    # Правильный вызов с словарем
    replacement = '''ml_model.predict({
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "historical_df": historical_df
        })'''
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    path.write_text(content, encoding="utf-8")
    print("✅ Все вызовы заменены на формат со словарем!")
    
    # Проверяем результат
    new_matches = list(re.finditer(pattern, content, re.DOTALL))
    print(f"🔍 После замены: {len(new_matches)} вызовов с kwargs осталось")
else:
    # Проверяем, есть ли правильные вызовы
    correct_pattern = r'ml_model\.predict\(\s*\{[^}]+\}\s*\)'
    correct_matches = list(re.finditer(correct_pattern, content, re.DOTALL))
    if correct_matches:
        print(f"✅ Найдено {len(correct_matches)} правильных вызовов (со словарем)")
    else:
        print("⚠️ Вызовы ml_model.predict не найдены в ожидаемом формате")
        # Показываем все вызовы
        all_calls = re.findall(r'ml_model\.predict\([^)]+\)', content, re.DOTALL)
        print(f"📋 Все вызовы ml_model.predict ({len(all_calls)}):")
        for i, call in enumerate(all_calls, 1):
            print(f"   {i}. {call[:150]}...")

if content != original_content:
    print("💾 Файл main.py изменен и сохранен!")
else:
    print("ℹ️ Файл не был изменен")
