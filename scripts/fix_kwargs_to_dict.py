import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Ищем вызов с именованными аргументами (может быть многострочным)
pattern = r'ml_result\s*=\s*ml_model\.predict\(\s*home_team\s*=\s*home_team\s*,\s*away_team\s*=\s*away_team\s*,\s*match_date\s*=\s*match_date\s*,\s*historical_df\s*=\s*historical_df\s*\)'

if re.search(pattern, content, re.DOTALL):
    print("✅ Найден проблемный вызов ml_model.predict() с kwargs!")
    
    # Заменяем на передачу словаря
    replacement = '''ml_result = ml_model.predict({
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "historical_df": historical_df
        })'''
    
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    path.write_text(new_content, encoding="utf-8")
    print("💾 Файл main.py успешно обновлен! Теперь ML-модель получает словарь.")
else:
    print("⚠️ Паттерн с kwargs не найден в таком виде. Ищем любые вызовы...")
    matches = re.findall(r'ml_model\.predict\([^)]+\)', content, re.DOTALL)
    if matches:
        print(f"Найдено {len(matches)} вызовов ml_model.predict:")
        for i, m in enumerate(matches, 1):
            print(f"{i}. {m[:150]}...")
