import pandas as pd
from pathlib import Path

data_dir = Path('data/historical')
all_data = []

print('📂 Merging CSV files...')
csv_files = sorted(data_dir.glob('*.csv'))
csv_files = [f for f in csv_files if 'all_matches' not in f.name]

for csv_file in csv_files:
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig', low_memory=False)
        # Добавляем метаданные через copy() чтобы избежать фрагментации
        df = df.copy()
        df['source_file'] = csv_file.stem
        all_data.append(df)
        print(f'✅ {csv_file.name}: {len(df)} matches')
    except Exception as e:
        print(f'⚠️ {csv_file.name}: {e}')

print(f'\n🔗 Concatenating {len(all_data)} files...')
combined = pd.concat(all_data, ignore_index=True)
print(f'📊 Total before cleaning: {len(combined)} matches')

# Очищаем
critical_cols = ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']
available_cols = [c for c in critical_cols if c in combined.columns]
combined = combined.dropna(subset=available_cols)

# Парсим даты (умно: пробуем разные форматы)
if 'Date' in combined.columns:
    for fmt in ['%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d']:
        try:
            parsed = pd.to_datetime(combined['Date'], format=fmt, errors='coerce')
            if parsed.notna().sum() > len(combined) * 0.5:
                combined['Date'] = parsed
                print(f'✅ Dates parsed with format: {fmt}')
                break
        except:
            continue
    
    #Fallback: auto-detect
    if combined['Date'].isna().sum() > len(combined) * 0.5:
        combined['Date'] = pd.to_datetime(combined['Date'], dayfirst=True, errors='coerce')
        print('✅ Dates parsed with dayfirst=True')
    
    combined = combined.dropna(subset=['Date'])

# Убираем дубликаты
dedup_cols = [c for c in ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'Date'] if c in combined.columns]
combined = combined.drop_duplicates(subset=dedup_cols)

print(f'\n🎉 Final: {len(combined)} unique matches')
print(f'📅 Date range: {combined["Date"].min()} — {combined["Date"].max()}')
print(f'⚽ Unique teams: {combined["HomeTeam"].nunique()}')
print(f'🏆 Unique leagues: {combined["Div"].nunique() if "Div" in combined.columns else "N/A"}')

# Сохраняем
output = data_dir / 'all_matches_clean.csv'
combined.to_csv(output, index=False, encoding='utf-8')
print(f'\n💾 Saved to: {output}')
print(f'📦 Size: {output.stat().st_size / 1024 / 1024:.1f} MB')
