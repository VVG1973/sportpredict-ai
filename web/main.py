import logging
import os
import sys
from pathlib import Path
from typing import List, Dict

from fastapi import FastAPI, Request, Query, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import Database
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SportPredict AI", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_path)

WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "")


async def verify_auth(request: Request):
    """Простая проверка пароля через cookie"""
    if not WEB_PASSWORD:
        return
    password = request.cookies.get("web_password")
    if password != WEB_PASSWORD:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


async def get_db():
    db = Database()
    await db.init()
    try:
        yield db
    finally:
        await db.close()


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, page: int = Query(1, ge=1), db: Database = Depends(get_db)):
    stats = await _get_stats(db)
    predictions, total_count, total_pages = await _get_all_predictions(db, page=page, per_page=50)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "stats": stats,
            "predictions": predictions,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
        },
    )


@app.get("/api/stats")
async def api_stats(db: Database = Depends(get_db)):
    return await _get_stats(db)


@app.get("/api/predictions")
async def api_predictions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Database = Depends(get_db),
):
    predictions, total, pages = await _get_all_predictions(db, page, per_page)
    return {
        "predictions": predictions,
        "page": page,
        "total_pages": pages,
        "total_count": total,
    }


async def _get_stats(db: Database) -> Dict:
    try:
        stats = await db.get_stats()
        return {
            "total": stats["total"],
            "wins": stats["wins"],
            "losses": stats["losses"],
            "pending": stats["pending"],
            "winrate": round(stats["winrate"], 1),
            "roi": round(stats.get("roi", 0), 1),
            "profit": round(stats.get("profit", 0), 0),
        }
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        return {"total": 0, "wins": 0, "losses": 0, "pending": 0,
                "winrate": 0, "roi": 0, "profit": 0}


async def _get_all_predictions(db: Database, page: int = 1, per_page: int = 50) -> tuple:
    try:
        total_count = await db.conn.fetchval("SELECT COUNT(*) FROM predictions") or 0

        offset = (page - 1) * per_page
        rows = await db.conn.fetch(
            """
            SELECT fixture_id, home_team, away_team, match_date,
                   prediction, confidence, odds, result
            FROM predictions
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            per_page,
            offset,
        )

        predictions = []
        for row in rows:
            predictions.append({
                "fixture_id": row["fixture_id"],
                "home_team": row["home_team"] or "Команда 1",
                "away_team": row["away_team"] or "Команда 2",
                "prediction": row["prediction"] or "П1",
                "confidence": round((row["confidence"] or 0.75) * 100, 1),
                "odds": row["odds"] or 2.0,
                "result": row["result"],
                "date": str(row["match_date"])[:16].replace("T", " ") if row["match_date"] else "—",
            })

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        return predictions, total_count, total_pages

    except Exception as e:
        logger.error(f"Ошибка прогнозов: {e}")
        return [], 0, 0


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
