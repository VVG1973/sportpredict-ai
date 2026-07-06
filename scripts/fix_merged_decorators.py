from pathlib import Path
import re

web_file = Path("web/main.py")
content = web_file.read_text(encoding="utf-8")

# Исправляем слипшиеся декораторы: разделяем их переводом строки
content = re.sub(
    r'(@app\.get\([^)]+\))(@app\.get\([^)]+\))',
    r'\1\n\2',
    content
)

# Убираем дублирующийся декоратор для "/" (оставляем только один)
# Паттерн: два одинаковых @app.get("/") подряд
content = re.sub(
    r'(@app\.get\("/"[^)]*\))\s*\n\s*@app\.get\("/"[^)]*\)',
    r'\1',
    content
)

web_file.write_text(content, encoding="utf-8")
print("✅ Слипшиеся декораторы разделены и дубликаты удалены!")
