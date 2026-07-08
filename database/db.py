import os
import logging
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from config import settings

logger = logging.getLogger(__name__)

USE_POSTGRESQL = "postgresql" in settings.DATABASE_URL


class Database:
    def __init__(self):
        self.pool = None
        self.conn = None
        self._is_sqlite = not USE_POSTGRESQL

    async def init(self):
        db_url = settings.DATABASE_URL
        if not db_url:
            raise ValueError("DATABASE_URL не установлен!")

        if self._is_sqlite:
            import aiosqlite
            db_path = db_url.replace("sqlite+aiosqlite:///", "")
            self.conn = await aiosqlite.connect(db_path)
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA journal_mode=WAL")
            logger.info(f"📁 SQLite: {db_path}")
        else:
            import asyncpg
            self.pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
            self.conn = await self.pool.acquire()
            logger.info("📁 PostgreSQL (pool: 2-10)")

        await self._create_all_tables()

    def _convert_params(self, sql: str):
        """Конвертирует $1..$N параметры PostgreSQL в ? для SQLite"""
        import re
        return re.sub(r'\$\d+', '?', sql)

    async def _execute(self, sql: str, *args):
        """Выполняет SQL-запрос (совместимо с SQLite и PostgreSQL)"""
        if self._is_sqlite:
            await self.conn.execute(self._convert_params(sql), args)
            await self.conn.commit()
        else:
            await self.conn.execute(sql, *args)

    async def _fetch(self, sql: str, *args) -> list:
        """SELECT запрос — возвращает список строк"""
        if self._is_sqlite:
            cursor = await self.conn.execute(self._convert_params(sql), args)
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            return await self.conn.fetch(sql, *args)

    async def _fetchrow(self, sql: str, *args) -> Optional[dict]:
        """SELECT запрос — возвращает одну строку"""
        if self._is_sqlite:
            cursor = await self.conn.execute(self._convert_params(sql), args)
            row = await cursor.fetchone()
            return dict(row) if row else None
        else:
            row = await self.conn.fetchrow(sql, *args)
            return dict(row) if row else None

    async def _fetchval(self, sql: str, *args):
        """SELECT запрос — возвращает одно значение"""
        if self._is_sqlite:
            cursor = await self.conn.execute(self._convert_params(sql), args)
            row = await cursor.fetchone()
            return row[0] if row else None
        else:
            return await self.conn.fetchval(sql, *args)

    async def _create_all_tables(self):
        if self._is_sqlite:
            await self._execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    is_vip INTEGER DEFAULT 0,
                    vip_expires TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fixture_id TEXT UNIQUE,
                    home_team TEXT,
                    away_team TEXT,
                    match_date TEXT,
                    prediction TEXT,
                    confidence REAL,
                    odds REAL,
                    result TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    username TEXT,
                    plan TEXT,
                    invoice_id TEXT,
                    status TEXT DEFAULT 'pending',
                    expires_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS express_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    events_json TEXT,
                    total_odds REAL,
                    price REAL,
                    events_count INTEGER,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT UNIQUE,
                    user_id INTEGER,
                    username TEXT,
                    plan TEXT,
                    amount REAL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS user_favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    team_name TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(user_id, team_name)
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
        else:
            await self._execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    is_vip BOOLEAN DEFAULT FALSE,
                    vip_expires TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id SERIAL PRIMARY KEY,
                    fixture_id TEXT UNIQUE,
                    home_team TEXT,
                    away_team TEXT,
                    match_date TEXT,
                    prediction TEXT,
                    confidence DOUBLE PRECISION,
                    odds DOUBLE PRECISION,
                    result TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER UNIQUE,
                    username TEXT,
                    plan TEXT,
                    invoice_id TEXT,
                    status TEXT DEFAULT 'pending',
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS express_groups (
                    id SERIAL PRIMARY KEY,
                    events_json TEXT,
                    total_odds DOUBLE PRECISION,
                    price DOUBLE PRECISION,
                    events_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id SERIAL PRIMARY KEY,
                    invoice_id TEXT UNIQUE,
                    user_id INTEGER,
                    username TEXT,
                    plan TEXT,
                    amount DOUBLE PRECISION,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS user_favorites (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    team_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, team_name)
                )
            """)
            await self._execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id SERIAL PRIMARY KEY,
                    referrer_id INTEGER NOT NULL,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        logger.info("✅ Таблицы созданы")

    async def save_prediction(self, fixture_id, home, away, date, pred, conf, odds):
        try:
            await self._execute("""
                INSERT INTO predictions (fixture_id, home_team, away_team, match_date, prediction, confidence, odds, result)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                ON CONFLICT (fixture_id) DO UPDATE SET
                    home_team = EXCLUDED.home_team,
                    away_team = EXCLUDED.away_team,
                    match_date = EXCLUDED.match_date,
                    prediction = EXCLUDED.prediction,
                    confidence = EXCLUDED.confidence,
                    odds = EXCLUDED.odds,
                    result = 'pending'
            """, fixture_id, home, away, date, pred, conf, odds)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогноза: {e}")

    async def get_pending_predictions(self):
        try:
            rows = await self._fetch("""
                SELECT fixture_id, home_team, away_team, match_date, prediction
                FROM predictions
                WHERE result = 'pending' OR result IS NULL
                LIMIT 50
            """)
            return [(r["fixture_id"], r["home_team"], r["away_team"], r["match_date"], r["prediction"]) for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения pending: {e}")
            return []

    async def update_result(self, fixture_id, result):
        try:
            await self._execute(
                "UPDATE predictions SET result = $1 WHERE fixture_id = $2",
                result, fixture_id
            )
        except Exception as e:
            logger.error(f"Ошибка обновления: {e}")

    async def get_stats(self, since=None):
        try:
            if since:
                row = await self._fetchrow("""
                    SELECT
                        COUNT(*) as total,
                        COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins,
                        COALESCE(SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END), 0) as losses
                    FROM predictions WHERE created_at >= $1
                """, since)
            else:
                row = await self._fetchrow("""
                    SELECT
                        COUNT(*) as total,
                        COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins,
                        COALESCE(SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END), 0) as losses
                    FROM predictions
                """)

            total = int(row["total"] or 0)
            wins = int(row["wins"] or 0)
            losses = int(row["losses"] or 0)
            pending = total - wins - losses
            checked = wins + losses
            winrate = (wins / checked * 100) if checked > 0 else 0.0

            return {
                "total": total, "wins": wins, "losses": losses,
                "pending": pending, "winrate": winrate, "roi": 0.0, "profit": 0,
            }
        except Exception as e:
            logger.error(f"Ошибка статистики: {e}")
            return {"total": 0, "wins": 0, "losses": 0, "pending": 0, "winrate": 0.0, "roi": 0.0, "profit": 0}

    async def save_express_group(self, events, total_odds, price):
        try:
            events_json = json.dumps(events, ensure_ascii=False)
            row = await self._fetchrow("""
                INSERT INTO express_groups (events_json, total_odds, price, events_count)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, events_json, total_odds, price, len(events))
            return row["id"] if row else None
        except Exception as e:
            logger.error(f"Ошибка сохранения экспресса: {e}")
            return None

    async def get_express_group(self, group_id):
        try:
            row = await self._fetchrow(
                "SELECT events_json, total_odds, price, events_count FROM express_groups WHERE id = $1",
                group_id
            )
            if row:
                return {
                    "events": json.loads(row["events_json"]),
                    "total_odds": row["total_odds"],
                    "price": row["price"],
                    "events_count": row["events_count"],
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения экспресса: {e}")
            return None

    async def save_invoice(self, invoice_id, user_id, username, plan, amount):
        try:
            await self._execute("""
                INSERT INTO invoices (invoice_id, user_id, username, plan, amount, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                ON CONFLICT (invoice_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id, username = EXCLUDED.username,
                    plan = EXCLUDED.plan, amount = EXCLUDED.amount
            """, invoice_id, user_id, username, plan, amount)
        except Exception as e:
            logger.error(f"Ошибка сохранения инвойса: {e}")

    async def get_pending_invoices(self):
        try:
            rows = await self._fetch(
                "SELECT invoice_id, user_id, username, plan FROM invoices WHERE status = 'pending'"
            )
            return [{"invoice_id": r["invoice_id"], "user_id": r["user_id"],
                      "username": r["username"], "plan": r["plan"]} for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения инвойсов: {e}")
            return []

    async def mark_invoice_paid(self, invoice_id):
        try:
            await self._execute("UPDATE invoices SET status = 'paid' WHERE invoice_id = $1", invoice_id)
        except Exception as e:
            logger.error(f"Ошибка отметки оплаты: {e}")

    async def save_subscription(self, user_id, username, plan, invoice_id, expires_at):
        try:
            await self._execute("""
                INSERT INTO subscriptions (user_id, username, plan, invoice_id, status, expires_at)
                VALUES ($1, $2, $3, $4, 'active', $5)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username, plan = EXCLUDED.plan,
                    invoice_id = EXCLUDED.invoice_id, status = 'active', expires_at = EXCLUDED.expires_at
            """, user_id, username, plan, invoice_id, expires_at)
        except Exception as e:
            logger.error(f"Ошибка сохранения подписки: {e}")

    async def get_expired_subscriptions(self):
        try:
            now = datetime.now(timezone.utc)
            rows = await self._fetch(
                "SELECT user_id, username FROM subscriptions WHERE status = 'active' AND expires_at < $1", now
            )
            return [{"user_id": r["user_id"], "username": r["username"]} for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения истёкших: {e}")
            return []

    async def deactivate_subscription(self, user_id):
        try:
            await self._execute("UPDATE subscriptions SET status = 'expired' WHERE user_id = $1", user_id)
        except Exception as e:
            logger.error(f"Ошибка деактивации: {e}")

    async def add_favorite_team(self, user_id: int, team_name: str) -> bool:
        try:
            await self._execute("""
                INSERT INTO user_favorites (user_id, team_name) VALUES ($1, $2)
                ON CONFLICT (user_id, team_name) DO NOTHING
            """, user_id, team_name)
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления избранного: {e}")
            return False

    async def remove_favorite_team(self, user_id: int, team_name: str) -> bool:
        try:
            await self._execute("DELETE FROM user_favorites WHERE user_id = $1 AND team_name = $2", user_id, team_name)
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления избранного: {e}")
            return False

    async def get_user_favorites(self, user_id: int) -> list:
        try:
            rows = await self._fetch("SELECT team_name FROM user_favorites WHERE user_id = $1", user_id)
            return [r["team_name"] for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения избранного: {e}")
            return []

    async def get_team_followers(self, team_name: str) -> list:
        try:
            if self._is_sqlite:
                rows = await self._fetch(
                    "SELECT uf.user_id, u.username FROM user_favorites uf JOIN users u ON uf.user_id = u.user_id WHERE uf.team_name = $1",
                    team_name
                )
            else:
                rows = await self._fetch(
                    """SELECT u.user_id, u.username FROM user_favorites uf
                       JOIN users u ON uf.user_id = u.user_id WHERE uf.team_name = $1""",
                    team_name
                )
            return [(r["user_id"], r["username"]) for r in rows]
        except Exception:
            return []

    async def get_user_follows(self, user_id: int) -> list:
        return await self.get_user_favorites(user_id)

    async def follow_team(self, user_id: int, username: str, team_name: str) -> bool:
        return await self.add_favorite_team(user_id, team_name)

    async def unfollow_team(self, user_id: int, team_name: str) -> bool:
        return await self.remove_favorite_team(user_id, team_name)

    async def add_referral(self, referrer_id: int, user_id: int, username: str) -> bool:
        try:
            await self._execute("""
                INSERT INTO referrals (referrer_id, user_id, username, created_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO NOTHING
            """, referrer_id, user_id, username)
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления реферала: {e}")
            return False

    async def get_referral_by_user(self, user_id: int):
        try:
            return await self._fetchrow("SELECT * FROM referrals WHERE user_id = $1", user_id)
        except Exception as e:
            logger.error(f"Ошибка получения реферала: {e}")
            return None

    async def get_user_referrals(self, user_id: int) -> list:
        try:
            rows = await self._fetch(
                "SELECT username, created_at FROM referrals WHERE referrer_id = $1 ORDER BY created_at DESC", user_id
            )
            return [{"username": r["username"], "created_at": r["created_at"]} for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения рефералов: {e}")
            return []

    async def get_user_stats(self, user_id: int):
        try:
            teams = await self.get_user_favorites(user_id)
            return {"views": 0, "votes": 0, "follows": len(teams), "teams": teams}
        except Exception as e:
            return {"views": 0, "votes": 0, "follows": 0, "teams": []}

    async def get_referral_stats(self, user_id: int) -> dict:
        try:
            row = await self._fetchrow("SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id = $1", user_id)
            return {"total": row["cnt"] if row else 0}
        except Exception as e:
            return {"total": 0}

    async def close(self):
        if self._is_sqlite and self.conn:
            await self.conn.close()
            self.conn = None
        elif self.conn:
            await self.pool.release(self.conn)
            self.conn = None
        if self.pool:
            await self.pool.close()
            self.pool = None
