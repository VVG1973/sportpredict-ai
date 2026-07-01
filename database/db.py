import asyncpg
import os
import aiosqlite
import logging
logger = logging.getLogger(__name__)
from pathlib import Path

import os
import os

def _get_safe_db_path():
    import os
    import tempfile
    from pathlib import Path

    # 1. Пытаемся использовать Railway Volume
    vol = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if vol:
        try:
            os.makedirs(vol, exist_ok=True)
            test_file = Path(vol) / ".write_test"
            test_file.touch(exist_ok=True)
            test_file.unlink(missing_ok=True)
            db_path = Path(vol) / "bot.db"
            print(f"📁 Используем Railway Volume: {db_path}")
            return str(db_path)
        except Exception as e:
            print(f"⚠️ Railway Volume {vol} недоступен для записи ({e}).")

    # 2. Резервный вариант: локальная папка /app/data
    app_data = Path("/app/data")
    try:
        app_data.mkdir(parents=True, exist_ok=True)
        test_file = app_data / ".write_test"
        test_file.touch(exist_ok=True)
        test_file.unlink(missing_ok=True)
        db_path = app_data / "bot.db"
        print(f"📁 Используем локальную папку (эфемерную): {db_path}")
        return str(db_path)
    except Exception as e:
        print(f"⚠️ /app/data недоступен ({e}).")

    # 3. Крайний случай: /tmp
    db_path = Path(tempfile.gettempdir()) / "bot.db"
    print(f"📁 Используем /tmp (эфемерную): {db_path}")
    return str(db_path)

class Database:
    def __init__(self, db_path: str = "data/predictions.db"):
        self.db_path = _get_safe_db_path()
        self.conn = None
    
    async def init(self):
        """Инициализация подключения к PostgreSQL"""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL не установлен в переменных окружения!")
        
        self.conn = await asyncpg.connect(db_url)
        print("📁 Подключено к PostgreSQL")
        
        # Создаем таблицы если их нет
        try:
            await self.create_tables()
        except Exception:
            pass  # Ignore race conditions during table creation
        
        # Таблица прогнозов с колонкой result
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
        
        # Добавляем колонку result, если её нет
        try:
            await self.conn.execute("ALTER TABLE predictions ADD COLUMN result TEXT DEFAULT 'pending'")
            pass  # asyncpg uses autocommit
        except Exception:
            pass
        
        # Таблица подписок
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
        
        # Таблица экспресс-групп
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
        
        # Таблица инвойсов
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
        
        # Таблица любимых команд
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_favorites (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                team_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, team_name)
            )
        """)
        

        # Таблица рефералов
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id INTEGER NOT NULL,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        pass  # asyncpg uses autocommit
        logger.info("✅ БД инициализирована")
    
    # === ПРОГНОЗЫ ===
    

    async def create_tables(self):
        """Создает таблицы в PostgreSQL если их нет"""
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
            CREATE TABLE IF NOT EXISTS favorite_teams (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                team_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                match_id TEXT,
                home_team TEXT,
                away_team TEXT,
                prediction TEXT,
                confidence DOUBLE PRECISION,
                odds DOUBLE PRECISION,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("✅ Таблицы PostgreSQL созданы/проверены")

    async def save_prediction(self, fixture_id, home, away, date, pred, conf, odds):
        try:
            await self.conn.execute("""
                INSERT OR REPLACE INTO predictions 
                (fixture_id, home_team, away_team, match_date, prediction, confidence, odds, result)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (fixture_id, home, away, date, pred, conf, odds))
            pass  # asyncpg uses autocommit
        except Exception as e:
            logger.error(f"Ошибка сохранения прогноза: {e}")
    
    async def get_pending_predictions(self):
        """Возвращает список непроверенных прогнозов"""
        try:
            cursor = await self.conn.execute(
                "SELECT fixture_id, home_team, away_team, match_date, prediction FROM predictions WHERE result = 'pending' OR result IS NULL LIMIT 50"
            )
            return await cursor
        except Exception as e:
            pass  # Suppress asyncpg noise
            return []
    
    async def update_result(self, fixture_id, result):
        """Обновляет результат прогноза (win/loss)"""
        try:
            await self.conn.execute(
                "UPDATE predictions SET result = ? WHERE fixture_id = ?",
                (result, fixture_id)
            )
            pass  # asyncpg uses autocommit
        except Exception as e:
            logger.error(f"Ошибка обновления результата: {e}")
    
    # === СТАТИСТИКА ===
    
    async def get_stats(self):
        try:
            cursor = await self.conn.fetch("SELECT COUNT(*) FROM predictions")
            total = (await cursor.fetchone())[0]
            
            cursor_wins = await self.conn.execute("SELECT COUNT(*) FROM predictions WHERE result = 'win'")
            wins = (await cursor_wins.fetchone())[0]
            
            cursor_losses = await self.conn.execute("SELECT COUNT(*) FROM predictions WHERE result = 'loss'")
            losses = (await cursor_losses.fetchone())[0]
            
            pending = total - wins - losses
            checked = wins + losses
            winrate = (wins / checked * 100) if checked > 0 else 0.0
            
            # Рассчитываем ROI (примерный, на основе средних коэффициентов)
            roi = 0.0
            if checked > 0:
                # Упрощенный расчет: если винрейт > 50%, ROI положительный
                roi = (winrate - 50) * 2  # Примерная формула
            
            return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "winrate": winrate,
                "roi": roi
            }
        except Exception as e:
            logger.error(f"Ошибка статистики: {e}")
            return {"total": 0, "wins": 0, "losses": 0, "pending": 0, "winrate": 0.0, "roi": 0.0}
    
    # === ЭКСПРЕССЫ ===
    
    async def save_express_group(self, events, total_odds, price):
        try:
            events_json = json.dumps(events, ensure_ascii=False)
            cursor = await self.conn.execute("""
                INSERT INTO express_groups (events_json, total_odds, price, events_count)
                VALUES (?, ?, ?, ?)
            """, (events_json, total_odds, price, len(events)))
            pass  # asyncpg uses autocommit
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка сохранения экспресса: {e}")
            return None
    
    async def get_express_group(self, group_id):
        try:
            cursor = await self.conn.execute(
                "SELECT events_json, total_odds, price, events_count FROM express_groups WHERE id = ?",
                (group_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "events": json.loads(row[0]),
                    "total_odds": row[1],
                    "price": row[2],
                    "events_count": row[3]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения экспресса: {e}")
            return None
    
    # === ОПЛАТА (КРИПТО) ===
    
    async def save_invoice(self, invoice_id, user_id, username, plan, amount):
        try:
            await self.conn.execute("""
                INSERT OR REPLACE INTO invoices 
                (invoice_id, user_id, username, plan, amount, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (invoice_id, user_id, username, plan, amount))
            pass  # asyncpg uses autocommit
        except Exception as e:
            logger.error(f"Ошибка сохранения инвойса: {e}")
    
    async def get_pending_invoices(self):
        try:
            cursor = await self.conn.execute(
                "SELECT invoice_id, user_id, username, plan FROM invoices WHERE status = 'pending'"
            )
            rows = cursor
            return [{"invoice_id": r[0], "user_id": r[1], "username": r[2], "plan": r[3]} for r in rows]
        except Exception as e:
            pass  # Suppress asyncpg noise
            return []
    
    async def mark_invoice_paid(self, invoice_id):
        try:
            await self.conn.execute(
                "UPDATE invoices SET status = 'paid' WHERE invoice_id = ?", (invoice_id,)
            )
            pass  # asyncpg uses autocommit
        except Exception as e:
            logger.error(f"Ошибка обновления инвойса: {e}")
    
    # === VIP ПОДПИСКИ ===
    
    async def save_subscription(self, user_id, username, plan, invoice_id, expires_at):
        try:
            await self.conn.execute("""
                INSERT OR REPLACE INTO subscriptions 
                (user_id, username, plan, invoice_id, status, expires_at)
                VALUES (?, ?, ?, ?, 'active', ?)
            """, (user_id, username, plan, invoice_id, expires_at))
            pass  # asyncpg uses autocommit
        except Exception as e:
            logger.error(f"Ошибка сохранения подписки: {e}")
    
    async def get_expired_subscriptions(self):
        try:
            now = TIMESTAMP.now().isoformat()
            cursor = await self.conn.execute(
                "SELECT user_id, username FROM subscriptions WHERE status = 'active' AND expires_at < ?", (now,)
            )
            rows = cursor
            return [{"user_id": r[0], "username": r[1]} for r in rows]
        except Exception as e:
            logger.error(f"Ошибка получения истёкших подписок: {e}")
            return []
    
    async def deactivate_subscription(self, user_id):
        try:
            await self.conn.execute(
                "UPDATE subscriptions SET status = 'expired' WHERE user_id = ?", (user_id,)
            )
            pass  # asyncpg uses autocommit
        except Exception as e:
            logger.error(f"Ошибка деактивации подписки: {e}")
    
    # === ЛЮБИМЫЕ КОМАНДЫ ===
    
    async def add_favorite_team(self, user_id: int, team_name: str) -> bool:
        try:
            await self.conn.execute(
                "INSERT OR IGNORE INTO user_favorites (user_id, team_name) VALUES (?, ?)",
                (user_id, team_name)
            )
            pass  # asyncpg uses autocommit
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления избранного: {e}")
            return False
    
    async def remove_favorite_team(self, user_id: int, team_name: str) -> bool:
        try:
            await self.conn.execute(
                "DELETE FROM user_favorites WHERE user_id = ? AND team_name = ?",
                (user_id, team_name)
            )
            pass  # asyncpg uses autocommit
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления избранного: {e}")
            return False
    
    async def get_user_favorites(self, user_id: int) -> list:
        try:
            cursor = await self.conn.execute(
                "SELECT team_name FROM user_favorites WHERE user_id = ?", (user_id,)
            )
            rows = cursor
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения избранного: {e}")
            return []
    
    async def get_team_followers(self, team_name: str) -> list:
        try:
            cursor = await self.conn.execute(
                "SELECT user_id FROM user_favorites WHERE team_name = ?", (team_name,)
            )
            rows = cursor
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения подписчиков: {e}")
            return []
    
    # === АЛИАСЫ ДЛЯ СОВМЕСТИМОСТИ ===
    
    async def get_user_follows(self, user_id: int) -> list:
        return await self.get_user_favorites(user_id)
    
    async def follow_team(self, user_id: int, username: str, team_name: str) -> bool:
        return await self.add_favorite_team(user_id, team_name)
    
    async def unfollow_team(self, user_id: int, team_name: str) -> bool:
        return await self.remove_favorite_team(user_id, team_name)
    
    # === ЗАКРЫТИЕ ===
    
    async def close(self):
        if self.conn:
            await self.conn.close()

    # === РЕФЕРАЛЬНАЯ ПРОГРАММА ===
    
        async def add_referral(self, referrer_id: int, user_id: int, username: str) -> bool:
        """Добавить реферала"""
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
        """Получить реферала по user_id"""
        try:
            cursor = await self.conn.execute(
                "SELECT * FROM referrals WHERE user_id = ?", (user_id,)
            )
            return await cursor.fetchone()
        except Exception as e:
            logger.error(f"Ошибка получения реферала: {e}")
            return None
    
    async def get_user_referrals(self, user_id: int) -> list:
        """Получить всех рефералов пользователя"""
        try:
            cursor = await self.conn.execute(
                "SELECT username, created_at FROM referrals WHERE referrer_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            rows = cursor
            return [{"username": row[0], "created_at": row[1]} for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения рефералов: {e}")
            return []
    

    async def get_user_stats(self, user_id: int):
        """Получает статистику конкретного пользователя"""
        try:
            teams = []
            follows = 0
            # Пытаемся получить любимые команды из возможных таблиц
            for table in ["favorite_teams", "user_teams", "followed_teams"]:
                for col in ["team_name", "team", "name"]:
                    try:
                        cursor = await self.conn.execute(
                            f"SELECT {col} FROM {table} WHERE user_id = ?", (user_id,)
                        )
                        rows = cursor
                        if rows:
                            teams = [row[0] for row in rows]
                            follows = len(teams)
                            break
                    except Exception:
                        continue
                if teams:
                    break
                    
            return {
                "views": 0,
                "votes": 0,
                "follows": follows,
                "teams": teams
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователя: {e}")
            return {"views": 0, "votes": 0, "follows": 0, "teams": []}

    async def get_referral_stats(self, user_id: int) -> dict:
        """Получить статистику рефералов"""
        try:
            cursor = await self.conn.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
            )
            total = (await cursor.fetchone())[0]
            return {"total": total}
        except Exception as e:
            logger.error(f"Ошибка получения статистики рефералов: {e}")
            return {"total": 0}
