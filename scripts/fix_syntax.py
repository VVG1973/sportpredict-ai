from pathlib import Path

path = Path("main.py")
if not path.exists():
    print("❌ main.py не найден")
    exit()

lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

new_lines = []
skip = False
fixed = False

for line in lines:
    # Находим начало сломанного блока
    if 'personal_text = (' in line and not fixed:
        skip = True
        fixed = True
        indent = '                    '
        # Вставляем правильный блок с экранированными \n
        new_lines.append(f'{indent}personal_text = (\n')
        new_lines.append(f'{indent}    f"⚡ <b>Прогноз на вашу команду!</b>\\n\\n"\n')
        new_lines.append(f'{indent}    f"{{sport}} | <i>{{league}}</i>\\n"\n')
        new_lines.append(f'{indent}    f"🏟 <b>{{home_team}}</b> — <b>{{away_team}}</b>\\n"\n')
        new_lines.append(f'{indent}    f"📅 <i>{{date_ru}}</i>\\n\\n"\n')
        new_lines.append(f'{indent}    f"🎯 <b>Прогноз:</b> {{pred[\'prediction\']}}\\n"\n')
        new_lines.append(f'{indent}    f"📊 <b>Уверенность:</b> {{pred[\'confidence\']:.0%}}\\n"\n')
        new_lines.append(f'{indent}    f"💰 <b>Коэф:</b> {{pred[\'odds_est\']}}\\n\\n"\n')
        new_lines.append(f'{indent}    f"━━━━━━━━━━━━━━━━━━━━━\\n"\n')
        new_lines.append(f'{indent}    f"⚠️ <i>Ответственная игра. 18+</i>"\n')
        new_lines.append(f'{indent})\n')
        continue
    
    # Пропускаем старые сломанные строки, пока не найдем закрывающую скобку
    if skip:
        if line.strip() == ')' or ('18+</i>' in line and ')' in line):
            skip = False
        continue
        
    new_lines.append(line)

path.write_text("".join(new_lines), encoding="utf-8")
print("✅ Ошибка синтаксиса (незакрытая кавычка на строке 228) успешно исправлена!")
