from pathlib import Path

req_file = Path("requirements.txt")
content = req_file.read_text(encoding="utf-8")

if "asyncpg" not in content:
    content += "\nasyncpg>=0.29.0\n"
    req_file.write_text(content, encoding="utf-8")
    print("✅ asyncpg добавлен в requirements.txt")
else:
    print("ℹ️ asyncpg уже есть в requirements.txt")
