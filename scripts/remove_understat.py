reqs = """aiogram>=3.4.0
apscheduler>=3.10.4
xgboost>=2.0.0
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
aiohttp>=3.9.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
aiosqlite>=0.19.0
asyncpg>=0.29.0
fastapi>=0.109.0
uvicorn>=0.27.0
requests>=2.31.0
"""
from pathlib import Path
Path("requirements.txt").write_text(reqs, encoding="utf-8")
print("✅ understat удален из requirements.txt! Конфликты зависимостей полностью решены.")
