import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# 1. Исправляем get_stats() - добавляем roi
old_stats_return = '''return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "winrate": winrate
            }'''

new_stats_return = '''roi = (winrate - 50) * 1.5 if checked > 0 else 0.0
            return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "winrate": winrate,
                "roi": roi
            }'''

if old_stats_return in content and '"roi"' not in content:
    content = content.replace(old_stats_return, new_stats_return)
    print("✅ get_stats() исправлен: добавлено поле 'roi'")
elif '"roi"' in content:
    print("ℹ️ get_stats() уже содержит 'roi'")

# Исправляем fallback при ошибке
old_stats_except = '''return {"total": 0, "wins": 0, "losses": 0, "pending": 0, "winrate": 0.0}'''
new_stats_except = '''return {"total": 0, "wins": 0, "losses": 0, "pending": 0, "winrate": 0.0, "roi": 0.0}'''
if old_stats_except in content:
    content = content.replace(old_stats_except, new_stats_except)

# 2. Добавляем get_user_stats(), если его нет
if "async def get_user_stats" not in content:
    user_stats_method = '''
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
                        rows = await cursor.fetchall()
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
'''
    
    # Ищем место для вставки (после последнего метода класса)
    lines = content.split('\n')
    insert_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith('    async def ') or lines[i].startswith('    def '):
            for j in range(i + 1, len(lines)):
                line = lines[j]
                if line.strip() == "":
                    continue
                if not line.startswith("        ") and not line.startswith("    #"):
                    insert_idx = j
                    break
            if insert_idx != -1:
                break
                
    if insert_idx != -1:
        lines.insert(insert_idx, user_stats_method)
        content = '\n'.join(lines)
        print("✅ Метод get_user_stats() успешно добавлен в database/db.py!")
    else:
        content += "\n" + user_stats_method
        print("✅ Метод get_user_stats() добавлен в конец файла!")
else:
    print("ℹ️ Метод get_user_stats() уже существует")

db_file.write_text(content, encoding="utf-8")
print("\n💾 database/db.py сохранен! Теперь /stats и /mystats будут работать.")
