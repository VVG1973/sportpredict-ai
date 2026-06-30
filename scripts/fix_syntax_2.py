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
    # Находим начало сломанного блока admin_text
    if 'admin_text = "🔓 <b>ДЕТАЛИ ЭКСПРЕССОВ' in line and not fixed:
        skip = True
        fixed = True
        indent = '            '
        # Вставляем правильный блок с экранированными \n
        new_lines.append(f'{indent}admin_text = "🔓 <b>ДЕТАЛИ ЭКСПРЕССОВ (только для вас)</b>\\n\\n"\n')
        new_lines.append(f'{indent}for express in admin_express_details:\n')
        new_lines.append(f'{indent}    admin_text += f"<b>{{express[\'title\']}}</b>\\n"\n')
        new_lines.append(f'{indent}    admin_text += f"━━━━━━━━━━━━━━━━━━━━━\\n"\n')
        new_lines.append(f'{indent}    for i, ev in enumerate(express["events"], 1):\n')
        new_lines.append(f'{indent}        match = ev.get("match", {{}})\n')
        new_lines.append(f'{indent}        home = match.get("home_team", "?")\n')
        new_lines.append(f'{indent}        away = match.get("away_team", "?")\n')
        new_lines.append(f'{indent}        sport = match.get("sport", "⚽")\n')
        new_lines.append(f'{indent}        league = match.get("league", "")\n')
        new_lines.append(f'{indent}        date_str = match.get("date", "")[:16].replace("T", " ")\n')
        new_lines.append(f'{indent}        prediction = ev.get("prediction", "?")\n')
        new_lines.append(f'{indent}        confidence = ev.get("confidence", 0)\n')
        new_lines.append(f'{indent}        odds = ev.get("odds_est", 2.0)\n')
        new_lines.append(f'{indent}        admin_text += (\n')
        new_lines.append(f'{indent}            f"<b>{{i}}.</b> {{sport}} | <i>{{league}}</i>\\n"\n')
        new_lines.append(f'{indent}            f"🏟 <b>{{home}}</b> — <b>{{away}}</b>\\n"\n')
        new_lines.append(f'{indent}            f"📅 <i>{{date_str}}</i>\\n"\n')
        new_lines.append(f'{indent}            f"🎯 <b>Исход: {{prediction}}</b>\\n"\n')
        new_lines.append(f'{indent}            f"📊 Уверенность: {{confidence:.0%}}\\n"\n')
        new_lines.append(f'{indent}            f"💰 Коэф: {{odds}}\\n\\n"\n')
        new_lines.append(f'{indent}        )\n')
        new_lines.append(f'{indent}    admin_text += (\n')
        new_lines.append(f'{indent}        f"💵 <b>Цена:</b> {{express[\'price\']}}₽\\n"\n')
        new_lines.append(f'{indent}        f"📈 <b>Общий коэф:</b> {{express[\'total_odds\']:.2f}}\\n\\n"\n')
        new_lines.append(f'{indent}    )\n')
        new_lines.append(f'{indent}admin_text += "━━━━━━━━━━━━━━━━━━━━━\\n"\n')
        new_lines.append(f'{indent}admin_text += f"📤 Всего опубликовано экспрессов: {{express_published}}"\n')
        continue
    
    # Пропускаем старые сломанные строки, пока не найдем конец блока
    if skip:
        # Ищем строку с отправкой админу (конец блока)
        if 'await publisher.bot.send_message' in line or ('chat_id=settings.ADMIN_ID' in line):
            skip = False
            new_lines.append(line)  # Возвращаем строку отправки
        continue
        
    new_lines.append(line)

path.write_text("".join(new_lines), encoding="utf-8")
print("✅ Вторая ошибка синтаксиса (admin_text на строке 352) успешно исправлена!")
