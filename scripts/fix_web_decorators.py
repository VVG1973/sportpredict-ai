from pathlib import Path
import re

web_file = Path("web/main.py")
content = web_file.read_text(encoding="utf-8")

# Ищем паттерн: два декоратора @app.get подряд без функции между ними
# Например: @app.get("/", ...)\n@app.get("/stats", ...)
pattern = r'(@app\.get\([^)]+\)[\s\n]+)(@app\.get\([^)]+\))'

if re.search(pattern, content):
    print("⚠️ Найден дублирующийся декоратор! Исправляем...")
    # Убираем первый дублирующийся декоратор, оставляем только один
    content = re.sub(pattern, r'\2', content)
    web_file.write_text(content, encoding="utf-8")
    print("✅ Дублирующийся декоратор удалён!")
else:
    print("ℹ️ Дублирующихся декораторов не найдено. Проверяем структуру...")
    # Выводим все декораторы и функции для ручной проверки
    matches = re.findall(r'^(@app\.(?:get|post|put|delete)\(.+\)|async def \w+)', content, re.MULTILINE)
    for m in matches:
        print(f"  {m}")
