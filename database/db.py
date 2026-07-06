import asyncpg
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "data/predictions.db"):
        self.conn: Optional[asyncpg.Connection] = None

    async def init(self):
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL не установлен в переменных окружения!")

        self.conn = await asyncpg.connect(db_url)
        logger.info("📁 Подключено к PostgreSQL")

        await self._create_all_tables()
        await self._migrate_columns()

    async def _migrate_columns(self):
        try:
            columns = await self.conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'predictions'
            """)
            column_names = [r["column_name"] for r in columns]
            
            if "match_date" not in column_names:
                await self.conn.execute("""
                    ALTER TABLE predictions 
                    ADD COLUMN match_date TEXT
                """)
                logger.info("✅ Добавлена колонка match_date в predictions")
            
            if "odds" not in column_names:
                await self.conn.execute("""
                    ALTER TABLE predictions 
                    ADD COLUMN odds DOUBLE PRECISION
                """)
                logger.info("✅ Добавлена колонка odds в predictions")
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка миграции колонок: {e}")

    async def _create_all_tables(self):
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                is_vip BOOLEAN DEFAULT FALSE,
                vip_expires TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self.conn.execute("""
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

        await self.conn.execute("""
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

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS express_groups (
                id SERIAL PRIMARY KEY,
                events_json TEXT,
                total_odds DOUBLE PRECISION,
                price DOUBLE PRECISION,
                events_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self.conn.execute("""
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

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_favorites (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, team_name)
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id INTEGER NOT NULL,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        logger.info("✅ БД инициализирована")

    async def save_prediction(self, fixture_id, home, away, date, pred, conf, odds):
        try:
            await self.conn.execute("""
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
            rows = await self.conn.fetch("""
                SELECT fixture_id, home_team, away_team, match_date, prediction
                FROM predictions
                WHERE result = 'pending' OR result IS NULL
                LIMIT 50
            """)
            return [(r["fixture_id"], r["home_team"], r["away_team"], r["match_date"], r["prediction"]) for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения pending прогнозов: {e}")
            return []

    async def update_result(self, fixture_id, result):
        try:
            await self.conn.execute(
                "UPDATE predictions SET result = $1 WHERE fixture_id = $2",
                result, fixture_id
            )
        except Exception as e:
            logger.error(f"Ошибка обновления результата: {e}")

    async def get_stats(self, since=None):
        """Возвращает статистику прогнозов. since — фильтр по дате создания."""
        try:
            if since:
                row = await self.conn.fetchrow("""
                    SELECT
                        COUNT(*) as total,
                        COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins,
                        COALESCE(SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END), 0) as losses
                    FROM predictions
                    WHERE created_at >= $1
                """, since)
            else:
                row = await self.conn.fetchrow("""
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
                "total": total,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "winrate": winrate,
            }
        except Exception as e:
            logger.error(f"Ошибка статистики: {e}")
            return {"total": 0, "wins": 0, "losses": 0, "pending": 0, "winrate": 0.0}

    async def save_express_group(self, events, total_odds, price):
        try:
            import json
            events_json = json.dumps(events, ensure_ascii=False)
            row = await self.conn.fetchrow("""
                INSERT INTO express_groups (events_json, total_odds, price, events_count)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, events_json, total_odds, price, len(events))
            return row["id"]
        except Exception as e:
            logger.error(f"Ошибка сохранения экспресса: {e}")
            return None

    async def get_express_group(self, group_id):
        try:
            import json
            row = await self.conn.fetchrow(
                "SELECT events_json, total_odds, price, events_count FROM express_groups WHERE id = $1",
                group_id
            )
            if row:
                return {
                    "events": json.loads(row["events_json"]),
                    "total_odds": row["total_odds"],
                    "price": row["price"],
                    "events_count": row["events_count"]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения экспресса: {e}")
            return None

    async def save_invoice(self, invoice_id, user_id, username, plan, amount):
        try:
            await self.conn.execute("""
                INSERT INTO invoices (invoice_id, user_id, username, plan, amount, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                ON CONFLICT (invoice_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    username = EXCLUDED.username,
                    plan = EXCLUDED.plan,
                    amount = EXCLUDED.amount
            """, invoice_id, user_id, username, plan, amount)
        except Exception as e:
            logger.error(f"Ошибка сохранения инвойса: {e}")

    async def get_pending_invoices(self):
        try:
            rows = await self.conn.fetch(
                "SELECT invoice_id, user_id, username, plan FROM invoices WHERE status = 'pending'"
            )
            return [{"invoice_id": r["invoice_id"], "user_id": r["user_id"], "username": r["username"], "plan": r["plan"]} for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения инвойсов: {e}")
            return []

    async def mark_invoice_paid(self, invoice_id):
        try:
            await self.conn.execute(
                "UPDATE invoices SET status = 'paid' WHERE invoice_id = $1",
                invoice_id
            )
        except Exception as e:
            logger.error(f"Ошибка отметки оплаты: {e}")

    async def save_subscription(self, user_id, username, plan, invoice_id, expires_at):
        try:
            await self.conn.execute("""
                INSERT INTO subscriptions (user_id, username, plan, invoice_id, status, expires_at)
                VALUES ($1, $2, $3, $4, 'active', $5)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    plan = EXCLUDED.plan,
                    invoice_id = EXCLUDED.invoice_id,
                    status = 'active',
                    expires_at = EXCLUDED.expires_at
            """, user_id, username, plan, invoice_id, expires_at)
        except Exception as e:
            logger.error(f"Ошибка сохранения подписки: {e}")

    async def get_expired_subscriptions(self):
        try:
            now = datetime.now(timezone.utc)
            rows = await self.conn.fetch(
                "SELECT user_id, username FROM subscriptions WHERE status = 'active' AND expires_at < $1",
                now
            )
            return [{"user_id": r["user_id"], "username": r["username"]} for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения истёкших подписок: {e}")
            return []

    async def deactivate_subscription(self, user_id):
        try:
            await self.conn.execute(
                "UPDATE subscriptions SET status = 'expired' WHERE user_id = $1",
                user_id
            )
        except Exception as e:
            logger.error(f"Ошибка деактивации подписки: {e}")

    async def add_favorite_team(self, user_id: int, team_name: str) -> bool:
        try:
            await self.conn.execute("""
                INSERT INTO user_favorites (user_id, team_name)
                VALUES ($1, $2)
                ON CONFLICT (user_id, team_name) DO NOTHING
            """, user_id, team_name)
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления избранного: {e}")
            return False

    async def remove_favorite_team(self, user_id: int, team_name: str) -> bool:
        try:
            await self.conn.execute(
                "DELETE FROM user_favorites WHERE user_id = $1 AND team_name = $2",
                user_id, team_name
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления избранного: {e}")
            return False

    async def get_user_favorites(self, user_id: int) -> list:
        try:
            rows = await self.conn.fetch(
                "SELECT team_name FROM user_favorites WHERE user_id = $1",
                user_id
            )
            return [r["team_name"] for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения избранного: {e}")
            return []

    async def get_team_followers(self, team_name: str) -> list:
        try:
            rows = await self.conn.fetch(
                "SELECT user_id FROM user_favorites WHERE team_name = $1",
                team_name
            )
            return [r["user_id"] for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения подписчиков: {e}")
            return []

    async def get_user_follows(self, user_id: int) -> list:
        return await self.get_user_favorites(user_id)

    async def follow_team(self, user_id: int, username: str, team_name: str) -> bool:
        return await self.add_favorite_team(user_id, team_name)

    async def unfollow_team(self, user_id: int, team_name: str) -> bool:
        return await self.remove_favorite_team(user_id, team_name)

    async def add_referral(self, referrer_id: int, user_id: int, username: str) -> bool:
        try:
            await self.conn.execute("""
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
            row = await self.conn.fetchrow(
                "SELECT * FROM referrals WHERE user_id = $1",
                user_id
            )
            return row
        except Exception as e:
            logger.error(f"Ошибка получения реферала: {e}")
            return None

    async def get_user_referrals(self, user_id: int) -> list:
        try:
            rows = await self.conn.fetch(
                "SELECT username, created_at FROM referrals WHERE referrer_id = $1 ORDER BY created_at DESC",
                user_id
            )
            return [{"username": r["username"], "created_at": r["created_at"]} for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения рефералов: {e}")
            return []

    async def get_user_stats(self, user_id: int):
        try:
            teams = await self.get_user_favorites(user_id)
            return {
                "views": 0,
                "votes": 0,
                "follows": len(teams),
                "teams": teams
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователя: {e}")
            return {"views": 0, "votes": 0, "follows": 0, "teams": []}

    async def get_referral_stats(self, user_id: int) -> dict:
        try:
            row = await self.conn.fetchrow(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = $1",
                user_id
            )
            return {"total": row[0] or 0}
        except Exception as e:
            logger.error(f"Ошибка получения статистики рефералов: {e}")
            return {"total": 0}

    async def close(self):
        if self.conn:
            await self.conn.close()