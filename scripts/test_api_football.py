"""
Тест подключения к API-Football
"""
import os
import httpx
from datetime import datetime

# Для локального теста вставьте ваш ключ сюда (в кавычках)
# Или скрипт попытается взять его из переменных окружения
API_KEY = os.getenv("API_FOOTBALL_KEY", "c044e6b190cd055586e06945783597f2")

if API_KEY == "ВСТАВЬТЕ_СЮДА_ВАШ_КЛЮЧ":
    print("⚠️ API-ключ не найден.")
    print("💡 Откройте scripts/test_api_football.py и впишите ваш ключ в переменную API_KEY.")
    exit(1)

today = datetime.now().strftime("%Y-%m-%d")
url = "https://v3.football.api-sports.io/fixtures"
headers = {
    "x-apisports-key": API_KEY,
    "x-rapidapi-host": "v3.football.api-sports.io"
}
params = {"date": today}

print(f"🌍 Запрашиваем матчи на {today}...")

try:
    with httpx.Client(headers=headers, timeout=30.0) as client:
        response = client.get(url, params=params)
        data = response.json()
        
        if data.get("errors"):
            print(f"❌ Ошибка API: {data['errors']}")
            exit(1)
            
        fixtures = data.get("response", [])
        print(f"✅ Успех! Найдено матчей на сегодня: {len(fixtures)}")
        
        if fixtures:
            print("\n📊 Первые 5 матчей:")
            for f in fixtures[:5]:
                home = f["teams"]["home"]["name"]
                away = f["teams"]["away"]["name"]
                league = f["league"]["name"]
                time = f["fixture"]["date"][11:16]
                print(f"   ⚽ {time} | {league} | {home} vs {away}")
        else:
            print("⚠️ На сегодня матчей не найдено.")
            
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
