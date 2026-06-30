from pathlib import Path
req = Path("requirements.txt")
c = req.read_text(encoding="utf-8")
if "jinja2" not in c.lower():
    c += "\njinja2>=3.1.0\n"
    req.write_text(c, encoding="utf-8")
    print("✅ jinja2 добавлен в requirements.txt!")
else:
    print("ℹ️ jinja2 уже есть")
