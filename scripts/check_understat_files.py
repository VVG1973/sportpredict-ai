"""
Проверка CSV файлов из Understat
"""
import csv
import os
from pathlib import Path

understat_dir = Path("data/historical/understat")

if not understat_dir.exists():
    print(f"❌ Папка не найдена: {understat_dir}")
    print("💡 Создайте папку и скачайте CSV файлы")
    exit(1)

csv_files = list(understat_dir.glob("*.csv"))
print(f"📂 Найдено файлов: {len(csv_files)}")
print()

for csv_file in csv_files:
    print(f"📊 {csv_file.name}:")
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            # Understat использует ; как разделитель
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)
            
            if not rows:
                print("   ❌ Пустой файл")
                continue
            
            # Проверяем первую команду
            first_team = rows[0]
            team_name = first_team.get('team', 'N/A').strip('"')
            xg = first_team.get('xG', 'N/A').strip('"')
            xga = first_team.get('xGA', 'N/A').strip('"')
            
            print(f"   ✅ Команд: {len(rows)}")
            print(f"   🏆 Первая: {team_name}")
            print(f"   📈 xG: {xg}, xGA: {xga}")
            
            # Проверяем наличие нужных колонок
            required = ['team', 'xG', 'xGA', 'NPxG']
            missing = [col for col in required if col not in first_team]
            if missing:
                print(f"   ⚠️ Отсутствуют колонки: {missing}")
            else:
                print(f"   ✅ Все нужные колонки на месте")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print()

print("=" * 60)
if len(csv_files) >= 30:
    print("🎉 Все 30 файлов скачаны! Готово к интеграции!")
elif len(csv_files) > 0:
    print(f"⏳ Скачано {len(csv_files)} из 30 файлов")
    print("💡 Продолжайте скачивание остальных файлов")
else:
    print("❌ Файлы не найдены")
