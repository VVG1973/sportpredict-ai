import re
from pathlib import Path

db_file = Path("database/db.py")
if not db_file.exists():
    print("❌ Файл database/db.py не найден!")
    exit(1)

content = db_file.read_text(encoding="utf-8")

# 1. Добавляем import asyncpg в начало файла
if "import asyncpg" not in content:
    imports_to_add = "import asyncpg\nimport os\n"
    content = imports_to_add + content
    print("✅ Добавлен import asyncpg")

# 2. Заменяем метод init() для PostgreSQL
old_init = r'async def init\(self\):.*?self\.conn = await aiosqlite\.connect\([^)]+\)'
new_init = '''async def init(self):
        """Инициализация подключения к PostgreSQL"""
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL не установлен в переменных окружения!")
        
        self.conn = await asyncpg.connect(db_url)
        print("📁 Подключено к PostgreSQL")
        
        # Создаем таблицы если их нет
        await self.create_tables()'''

content = re.sub(old_init, new_init, content, flags=re.DOTALL)
print("✅ Метод init() обновлен для PostgreSQL")

# 3. Добавляем метод create_tables() после init()
create_tables_method = '''

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
                confidence REAL,
                odds REAL,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("✅ Таблицы PostgreSQL созданы/проверены")
'''

# Ищем место после метода init() и вставляем create_tables()
init_end = content.find('async def init(self):')
if init_end != -1:
    # Находим конец метода init() (следующий метод или конец класса)
    next_method = content.find('\n    async def ', init_end + 1)
    if next_method == -1:
        next_method = content.find('\n    def ', init_end + 1)
    if next_method == -1:
        next_method = len(content)
    
    content = content[:next_method] + create_tables_method + content[next_method:]
    print("✅ Метод create_tables() добавлен")

db_file.write_text(content, encoding="utf-8")
print("\n💾 database/db.py успешно обновлен для PostgreSQL!")
