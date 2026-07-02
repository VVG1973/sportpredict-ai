from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import Database
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SportPredict AI")

static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_path)



async def get_table_columns(db, table_name: str) -> List[str]:
    """Получить список колонок таблицы"""
    try:
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        rows = await cursor.fetchall()
        return [row[1] for row in rows]
    except:
        return []


async def get_stats() -> Dict:
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
                "winrate": 0, "roi": 0, "profit": 0}


async def get_all_predictions(page: int = 1, per_page: int = 50) -> tuple:
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


@app.get("/", response_class=HTMLResponse)@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, page: int = Query(1, ge=1)):
    """Главная страница с пагинацией"""
    stats = await get_stats()
    predictions, total_count, total_pages = await get_all_predictions(page=page, per_page=50)
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "stats": stats,
            "predictions": predictions,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        }
    )


@app.get("/api/stats")
async def api_stats():
    return await get_stats()


@app.get("/api/predictions")
async def api_predictions(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200)):
    predictions, total, pages = await get_all_predictions(page, per_page)
    return {
        "predictions": predictions,
        "page": page,
        "total_pages": pages,
        "total_count": total
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
