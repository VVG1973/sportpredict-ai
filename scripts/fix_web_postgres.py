from pathlib import Path

web_file = Path("web/main.py")
content = web_file.read_text(encoding="utf-8")

# 1. Заменяем aiosqlite на Database из database/db.py
old_imports = """import aiosqlite
import logging
from typing import List, Dict"""

new_imports = """import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import Database
import logging
from typing import List, Dict"""

content = content.replace(old_imports, new_imports)

# 2. Убираем DB_PATH
content = content.replace('DB_PATH = "data/predictions.db"\n', '')

# 3. Переписываем get_stats() на asyncpg
old_stats = '''async def get_stats() -> Dict:
    """Получить статистику из БД"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN result IS NULL THEN 1 ELSE 0 END) as pending
                FROM predictions
            """)
            row = await cursor.fetchone()
            
            total = row[0] or 0
            wins = row[1] or 0
            losses = row[2] or 0
            pending = row[3] or 0
            
            completed = wins + losses
            winrate = (wins / completed * 100) if completed > 0 else 0
            
            avg_odds = 2.0
            profit = (wins * avg_odds - completed) * 100
            roi = (profit / (completed * 100) * 100) if completed > 0 else 0
            
            return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "winrate": round(winrate, 1),
                "roi": round(roi, 1),
                "profit": round(profit, 0)
            }
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        return {"total": 0, "wins": 0, "losses": 0, "pending": 0, 
                "winrate": 0, "roi": 0, "profit": 0}'''

new_stats = '''async def get_stats() -> Dict:
    """Получить статистику из PostgreSQL"""
    try:
        db = Database()
        await db.init()
        row = await db.conn.fetchrow("""
            SELECT 
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins,
                COALESCE(SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END), 0) as losses,
                COALESCE(SUM(CASE WHEN result IS NULL THEN 1 ELSE 0 END), 0) as pending
            FROM predictions
        """)
        await db.close()
        
        total = row["total"] or 0
        wins = row["wins"] or 0
        losses = row["losses"] or 0
        pending = row["pending"] or 0
        
        completed = wins + losses
        winrate = (wins / completed * 100) if completed > 0 else 0
        
        avg_odds = 2.0
        profit = (wins * avg_odds - completed) * 100
        roi = (profit / (completed * 100) * 100) if completed > 0 else 0
        
        return {
            "total": total, "wins": wins, "losses": losses, "pending": pending,
            "winrate": round(winrate, 1), "roi": round(roi, 1), "profit": round(profit, 0)
        }
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        return {"total": 0, "wins": 0, "losses": 0, "pending": 0, 
                "winrate": 0, "roi": 0, "profit": 0}'''

content = content.replace(old_stats, new_stats)

# 4. Переписываем get_all_predictions() на asyncpg
old_preds_func_start = 'async def get_all_predictions(page: int = 1, per_page: int = 50) -> tuple:'
old_preds_func_end = '        return [], 0, 0\n\n\n@app.get("/", response_class=HTMLResponse)'

new_preds = '''async def get_all_predictions(page: int = 1, per_page: int = 50) -> tuple:
    """Получить прогнозы из PostgreSQL с пагинацией"""
    try:
        db = Database()
        await db.init()
        
        total_count = await db.conn.fetchval("SELECT COUNT(*) FROM predictions") or 0
        
        offset = (page - 1) * per_page
        rows = await db.conn.fetch("""
            SELECT fixture_id, home_team, away_team, date, 
                   prediction, confidence, odds, result
            FROM predictions
            ORDER BY date DESC
            LIMIT $1 OFFSET $2
        """, per_page, offset)
        await db.close()
        
        predictions = []
        for row in rows:
            pred = {
                "fixture_id": row["fixture_id"],
                "home_team": row["home_team"] or "Команда 1",
                "away_team": row["away_team"] or "Команда 2",
                "prediction": row["prediction"] or "П1",
                "confidence": round((row["confidence"] or 0.75) * 100, 1),
                "odds": row["odds"] or 2.0,
                "result": row["result"],
                "date": str(row["date"])[:16].replace("T", " ") if row["date"] else "—"
            }
            predictions.append(pred)
        
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        return predictions, total_count, total_pages
        
    except Exception as e:
        logger.error(f"Ошибка прогнозов: {e}")
        import traceback
        traceback.print_exc()
        return [], 0, 0


@app.get("/", response_class=HTMLResponse)'''

# Находим и заменяем всю функцию get_all_predictions
import re
pattern = r'async def get_all_predictions\(page: int = 1, per_page: int = 50\) -> tuple:.*?(?=@app\.get\("/", response_class=HTMLResponse\))'
content = re.sub(pattern, new_preds, content, flags=re.DOTALL)

# 5. Исправляем имя шаблона: index.html -> dashboard.html (если ваш файл называется dashboard.html)
# Если ваш файл называется index.html, оставьте как есть
if "dashboard.html" in Path("templates").glob("*"):
    content = content.replace('name="index.html"', 'name="dashboard.html"')
    print("ℹ️ Шаблон переключен на dashboard.html")
else:
    print("ℹ️ Используется шаблон index.html")

web_file.write_text(content, encoding="utf-8")
print("✅ web/main.py переключен на PostgreSQL!")
