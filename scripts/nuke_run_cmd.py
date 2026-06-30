import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Ищем блок с командой /run и удаляем его до строки if __name__
pattern = r'(?:# === РУЧНОЙ ЗАПУСК PIPELINE[^\n]*\n)?@dp\.message\(Command\("run"\)\).*?(?=\nif __name__|$)'
new_content, count = re.subn(pattern, '', content, flags=re.DOTALL)

if count == 0:
    # Запасной вариант: удаляем всё от комментария "РУЧНОЙ ЗАПУСК" до конца
    pattern2 = r'# === РУЧНОЙ ЗАПУСК.*?(?=\nif __name__|$)'
    new_content, count = re.subn(pattern2, '', content, flags=re.DOTALL)

if count > 0:
    path.write_text(new_content, encoding="utf-8")
    print(f"✅ Успешно удалено {count} проблемных блоков с командой /run из main.py!")
    print("💾 Файл сохранен. Ошибка NameError больше не появится.")
else:
    print("⚠️ Скрипт не нашел блок. Возможно, он уже удален или имеет другой формат.")
