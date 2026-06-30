"""
Удаляет сломанный автозапуск и проверяет fix для ml_model.predict()
"""
import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# 1. Удаляем блок _auto_run_test
if "_auto_run_test" in content:
    # Удаляем от комментария до конца блока
    pattern = r'# === АВТОМАТИЧЕСКИЙ ТЕСТОВЫЙ ЗАПУСК PIPELINE ===.*?asyncio\.create_task\(_auto_run_test\(\)\)\n'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    print("✅ Блок _auto_run_test удален (исправлен crash loop)")

# 2. Проверяем, правильный ли вызов ml_model.predict()
wrong_call = r'ml_model\.predict\(\s*home_team=home_team'
if re.search(wrong_call, content):
    print("⚠️ Найден НЕПРАВИЛЬНЫЙ вызов ml_model.predict() с именованными аргументами!")
    print("   Исправляю...")
    
    # Правильный вызов с словарем
    correct_call = '''ml_result = ml_model.predict({
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "historical_df": historical_df
        })'''
    
    # Ищем и заменяем неправильный вызов
    pattern = r'ml_result\s*=\s*ml_model\.predict\(\s*home_team=home_team,\s*away_team=away_team,\s*match_date=match_date,\s*historical_df=historical_df\s*\)'
    content = re.sub(pattern, correct_call, content, flags=re.DOTALL)
    print("✅ Вызов ml_model.predict() исправлен (передается словарь)")
else:
    print("✅ Вызов ml_model.predict() уже правильный (или не найден)")

path.write_text(content, encoding="utf-8")
print("\n💾 main.py сохранен!")
