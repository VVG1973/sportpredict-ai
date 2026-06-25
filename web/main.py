from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import aiosqlite
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

DB_PATH = "data/predictions.db"


async def get_table_columns(db, table_name: str) -> List[str]:
    """Получить список колонок таблицы"""
    try:
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        rows = await cursor.fetchall()
        return [row[1] for row in rows]
    except:
        return []


async def get_stats() -> Dict:
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
                "winrate": 0, "roi": 0, "profit": 0}


async def get_all_predictions(page: int = 1, per_page: int = 50) -> tuple:
    """Получить ВСЕ прогнозы с пагинацией"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Получаем общее количество
            cursor = await db.execute("SELECT COUNT(*) FROM predictions")
            total_count = (await cursor.fetchone())[0] or 0
            
            # Получаем колонки
            columns = await get_table_columns(db, "predictions")
            
            if not columns:
                return [], 0, 0
            
            # Определяем колонку даты
            date_col = None
            if "match_date" in columns:
                date_col = "match_date"
            elif "date" in columns:
                date_col = "date"
            elif "created_at" in columns:
                date_col = "created_at"
            
            order_col = date_col if date_col else "fixture_id"
            
            # Вычисляем offset
            offset = (page - 1) * per_page
            
            query = f"""
                SELECT fixture_id, home_team, away_team, {date_col or 'created_at'}, 
                       prediction, confidence, odds_est, result
                FROM predictions
                ORDER BY {order_col} DESC
                LIMIT ? OFFSET ?
            """
            
            cursor = await db.execute(query, (per_page, offset))
            rows = await cursor.fetchall()
            
            predictions = []
            for row in rows:
                pred = {
                    "fixture_id": row[0],
                    "home_team": row[1] or "Команда 1",
                    "away_team": row[2] or "Команда 2",
                    "prediction": row[4] or "П1",
                    "confidence": round((row[5] or 0.75) * 100, 1),
                    "odds": row[6] or 2.0,
                    "result": row[7]
                }
                
                # Дата
                if row[3]:
                    pred["date"] = str(row[3])[:10]
                else:
                    pred["date"] = "—"
                
                predictions.append(pred)
            
            total_pages = (total_count + per_page - 1) // per_page
            
            return predictions, total_count, total_pages
            
    except Exception as e:
        logger.error(f"Ошибка прогнозов: {e}")
        import traceback
        traceback.print_exc()
        return [], 0, 0


@app.get("/", response_class=HTMLResponse)
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
