from pathlib import Path

req_file = Path("requirements.txt")
content = req_file.read_text(encoding="utf-8")

if "httpx" not in content:
    content += "\nhttpx>=0.27.0\n"
    req_file.write_text(content, encoding="utf-8")
    print("✅ httpx успешно добавлен в requirements.txt!")
else:
    print("ℹ️ httpx уже присутствует в файле.")
