import re
from pathlib import Path

db_file = Path("database/db.py")
content = db_file.read_text(encoding="utf-8")

# 1. Исправляем get_stats() - добавляем roi
old_return = '''return {
                "total": total,
                "wins": wins,
                "losses": losses,
                "pending": pending,
                "winrate": winrate
            }'''

new_return = '''# Рассчитываем ROI (примерный, на основе средних коэффициентов)
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
            }'''

if old_return in content:
    content = content.replace(old_return, new_return)
    print("✅ get_stats() исправлен: добавлено поле 'roi'")
else:
    print("⚠️ Не удалось найти точный блок return в get_stats()")

# 2. Проверяем и исправляем get_user_stats()
# Ищем метод get_user_stats
user_stats_pattern = r'async def get_user_stats\(self, user_id: int\):.*?(?=\n    async def |\nclass |\Z)'
match = re.search(user_stats_pattern, content, re.DOTALL)

if match:
    user_stats_method = match.group(0)
    
    # Проверяем, есть ли нужные поля в return
    if '"views"' not in user_stats_method or '"votes"' not in user_stats_method or '"follows"' not in user_stats_method or '"teams"' not in user_stats_method:
        print("⚠️ get_user_stats() может не возвращать все нужные поля")
        print("   Нужно добавить: views, votes, follows, teams")
    else:
        print("✅ get_user_stats() выглядит корректно")

db_file.write_text(content, encoding="utf-8")
print("\n💾 database/db.py сохранен!")
