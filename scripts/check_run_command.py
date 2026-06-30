import re
from pathlib import Path

main_path = Path("main.py")
content = main_path.read_text(encoding="utf-8")

# Ищем команду /run
if '@dp.message(Command("run"))' in content or '@router.message(Command("run"))' in content:
    print("✅ Команда /run найдена в коде")
    
    # Проверяем, где она находится
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'Command("run")' in line:
            print(f"   Строка {i+1}: {line.strip()}")
else:
    print("❌ Команда /run НЕ найдена в коде")
    print("💡 Нужно добавить её после определения диспетчера бота")
