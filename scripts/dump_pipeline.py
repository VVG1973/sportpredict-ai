import re
import os

print("🔍 Анализируем структуру проекта...")

# 1. Проверяем main.py
if os.path.exists('main.py'):
    with open('main.py', encoding='utf-8') as f:
        content = f.read()
    
    # Ищем функцию run_pipeline (или похожую по смыслу)
    match = re.search(r'((?:async\s+)?def\s+run_pipeline.*?)(?=\n(?:async\s+)?def\s|\nif\s+__name__|$)', content, re.DOTALL)
    
    if match:
        with open('pipeline_dump.txt', 'w', encoding='utf-8') as out:
            out.write(match.group(1))
        print("✅ Функция run_pipeline найдена и сохранена в pipeline_dump.txt")
    else:
        print("⚠️ Функция run_pipeline не найдена в main.py. Ищем другие точки входа...")

# 2. Проверяем real_sports_parser.py
parser_path = 'data_collectors/real_sports_parser.py'
if os.path.exists(parser_path):
    with open(parser_path, encoding='utf-8') as f:
        content2 = f.read()
    
    match2 = re.search(r'((?:async\s+)?def\s+get_matches.*?)(?=\n(?:async\s+)?def\s|\Z)', content2, re.DOTALL)
    if match2:
        with open('parser_dump.txt', 'w', encoding='utf-8') as out:
            out.write(match2.group(1))
        print("✅ Функция get_matches из real_sports_parser.py сохранена в parser_dump.txt")

print("\n" + "="*50)
print("📋 ГОТОВО! Пожалуйста, откройте файлы pipeline_dump.txt")
print("   и/или parser_dump.txt в Блокноте и скопируйте их")
print("   содержимое сюда в чат.")
print("="*50)
