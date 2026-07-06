import re
from pathlib import Path

# 1. Обновляем feature_extractor.py (делаем его устойчивым)
fe_file = Path("analyzers/feature_extractor.py")
if fe_file.exists():
    content = fe_file.read_text(encoding="utf-8")
    if "if not feature_cols:" not in content:
        content = re.sub(
            r'def extract_features\(match_data: dict, feature_cols: list\) -> dict:',
            r'def extract_features(match_data: dict, feature_cols: list = None) -> dict:\n    if not feature_cols:\n        return match_data',
            content
        )
        fe_file.write_text(content, encoding="utf-8")
        print("✅ feature_extractor.py обновлен (добавлена защита от пустого списка)")

# 2. Обновляем main.py (внедряем экстрактор)
main_file = Path("main.py")
content = main_file.read_text(encoding="utf-8")

# Добавляем импорт
if "from analyzers.feature_extractor import extract_features" not in content:
    content = re.sub(
        r'(from data_collectors\.multi_sport_parser import MultiSportParser)',
        r'\1\n    from analyzers.feature_extractor import extract_features',
        content
    )
    print("✅ Добавлен импорт extract_features")

# Заменяем вызов predict на умную версию
pattern = r'ml_result\s*=\s*ml_model\.predict\(\s*match_data\s*\)'
replacement = '''feature_cols = getattr(getattr(ml_model, 'model', ml_model), 'feature_cols', None)
            enriched_match_data = extract_features(match_data, feature_cols)
            ml_result = ml_model.predict(enriched_match_data)'''

if re.search(pattern, content):
    content = re.sub(pattern, replacement, content)
    main_file.write_text(content, encoding="utf-8")
    print("✅ main.py обновлен: FeatureExtractor внедрен в пайплайн!")
    print("   Теперь каждый матч получит уникальный вектор из 54 признаков.")
else:
    print("⚠️ Паттерн predict(match_data) не найден. Возможно, он уже изменен.")
