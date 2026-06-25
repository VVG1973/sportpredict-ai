"""
Скрипт для сбора исторических данных.
Запуск: python -m scripts.collect_historical_data
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_collectors.historical_data_collector import main

if __name__ == "__main__":
    asyncio.run(main())
