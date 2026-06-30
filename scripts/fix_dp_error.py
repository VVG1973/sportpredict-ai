from pathlib import Path
import re

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Удаляем блок, который был вставлен не в то место
# Ищем от "# === РУЧНОЙ ЗАПУСК" до "if __name__"
pattern = r'# === РУЧНОЙ ЗАПУСК PIPELINE.*?(?=if __name__ == "__main__":)'
new_content, count = re.subn(pattern, '', content, flags=re.DOTALL)

if count > 0:
    path.write_text(new_content, encoding="utf-8")
    print(f"✅ Успешно удалено {count} сломанных блоков из main.py!")
    print("💾 Файл сохранен. Теперь приложение должно запуститься без ошибок.")
else:
    print("⚠️ Паттерн не найден. Возможно, блок уже удален или имеет другой формат.")
