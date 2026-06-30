from pathlib import Path
import re

req_file = Path("requirements.txt")
if req_file.exists():
    content = req_file.read_text(encoding="utf-8")
    # Заменяем любое упоминание understat с версией на правильную
    new_content = re.sub(r'understat[^\n]*', 'understat==0.1.14', content)
    
    if new_content != content:
        req_file.write_text(new_content, encoding="utf-8")
        print("✅ Версия understat успешно исправлена на 0.1.14!")
    else:
        print("ℹ️ understat не найден или уже имеет правильную версию.")
else:
    print("❌ Файл requirements.txt не найден!")
