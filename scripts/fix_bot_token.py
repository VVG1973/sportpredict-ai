import re
from pathlib import Path

path = Path("main.py")
content = path.read_text(encoding="utf-8")

# Ищем проблемную строку и заменяем на безопасное чтение из переменных окружения
old_pattern = r'bot\s*=\s*Bot\(token=settings\.BOT_TOKEN\)'
new_code = "import os\n    bot = Bot(token=(os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN')))"

if re.search(old_pattern, content):
    content = re.sub(old_pattern, new_code, content)
    path.write_text(content, encoding="utf-8")
    print("✅ Ошибка с BOT_TOKEN успешно исправлена! Теперь токен берется напрямую из Railway.")
else:
    print("⚠️ Точное совпадение не найдено, пробуем прямую замену...")
    if "settings.BOT_TOKEN" in content:
        content = content.replace("settings.BOT_TOKEN", "(os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN'))")
        if "import os" not in content:
            content = "import os\n" + content
        path.write_text(content, encoding="utf-8")
        print("✅ Исправлено прямой заменой!")
    else:
        print("❌ Строка с BOT_TOKEN вообще не найдена в main.py")
