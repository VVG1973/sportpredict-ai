"""
Скрипт для объединения CSV файлов в один датасет.
Запуск: python scripts/merge_data.py
"""
import pandas as pd
from pathlib import Path


def merge_csv_files():
    data_dir = Path("data/historical")
    all_data = []
    
    print("📂 Ищу CSV файлы в data/historical/...")
    
    for csv_file in data_dir.glob("*.csv"):
        if "all_matches" in csv_file.name:
            continue  # Пропускаем уже объединённые файлы
        
        try:
            df = pd.read_csv(csv_file, encoding="utf-8-sig")
            df["source_file"] = csv_file.stem
            all_data.append(df)
            print(f"✅ Загружено: {csv_file.name} ({len(df)} матчей)")
        except Exception as e:
            print(f"⚠️ Ошибка: {csv_file.name}: {e}")
    
    if not all_data:
        print("❌ Нет данных для объединения")
        return
    
    combined = pd.concat(all_data, ignore_index=True)
    
    # Очищаем
    critical_cols = ["HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
    available_cols = [c for c in critical_cols if c in combined.columns]
    combined = combined.dropna(subset=available_cols)
    combined = combined.drop_duplicates()
    
    # Сохраняем
    output_path = data_dir / "all_matches_clean.csv"
    combined.to_csv(output_path, index=False, encoding="utf-8")
    
    print(f"\n🎉 Готово!")
    print(f"📊 Всего матчей: {len(combined)}")
    print(f"📁 Файл: {output_path}")
    
    if "HomeTeam" in combined.columns:
        unique_teams = combined["HomeTeam"].nunique()
        print(f"⚽ Уникальных команд: {unique_teams}")


if __name__ == "__main__":
    merge_csv_files()
