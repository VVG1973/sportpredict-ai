"""
Скрипт для добавления новых матчей в исторический датасет.
Скачивает данные за последнюю неделю и добавляет к существующим.

Запуск: python scripts/update_data.py
"""
import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import httpx
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class DataUpdater:
    BASE_URL = "https://www.football-data.co.uk/mmz4281"
    
    LEAGUES = {
        "E0": "English Premier League",
        "E1": "English Championship",
        "SP1": "Spanish La Liga",
        "I1": "Italian Serie A",
        "D1": "German Bundesliga",
        "F1": "French Ligue 1",
    }
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.main_file = self.data_dir / "all_matches_clean.csv"
    
    def get_current_season(self) -> str:
        """Определяет текущий сезон (например, '2425' для 2024-2025)"""
        now = datetime.now()
        if now.month >= 8:  # Сезон начинается в августе
            return f"{now.year % 100}{(now.year + 1) % 100}"
        else:
            return f"{(now.year - 1) % 100}{now.year % 100}"
    
    async def download_latest_csv(self, league_code: str, season: str) -> pd.DataFrame:
        """Скачивает CSV файл для одной лиги и сезона"""
        url = f"{self.BASE_URL}/{season}/{league_code}.csv"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Сохраняем с правильной кодировкой
                csv_path = self.data_dir / f"{league_code}_{season}_latest.csv"
                csv_path.write_bytes(response.content)
                
                df = pd.read_csv(csv_path, encoding="utf-8-sig")
                logger.info(f"✅ Скачано {len(df)} матчей: {league_code} {season}")
                
                # Удаляем временный файл
                csv_path.unlink()
                
                return df
        except Exception as e:
            logger.warning(f"⚠️ Не удалось скачать {league_code} {season}: {e}")
            return pd.DataFrame()
    
    def load_existing_data(self) -> pd.DataFrame:
        """Загружает существующий датасет"""
        if not self.main_file.exists():
            logger.warning("⚠️ Основной файл не найден, начинаем с нуля")
            return pd.DataFrame()
        
        df = pd.read_csv(self.main_file, encoding="utf-8")
        logger.info(f"📚 Загружено {len(df)} существующих матчей")
        return df
    
    def merge_data(self, old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """Объединяет старые и новые данные, убирая дубликаты"""
        if old_df.empty:
            return new_df
        if new_df.empty:
            return old_df
        
        # Объединяем
        combined = pd.concat([old_df, new_df], ignore_index=True)
        
        # Очищаем
        critical_cols = ["HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
        available_cols = [c for c in critical_cols if c in combined.columns]
        combined = combined.dropna(subset=available_cols)
        
        # Убираем дубликаты по ключевым полям
        dedup_cols = ["HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
        available_dedup = [c for c in dedup_cols if c in combined.columns]
        if "Date" in combined.columns:
            available_dedup.append("Date")
        
        combined = combined.drop_duplicates(subset=available_dedup)
        
        logger.info(f"🔗 После объединения: {len(combined)} матчей (добавлено {len(combined) - len(old_df)} новых)")
        return combined
    
    async def update(self):
        """Основной метод обновления данных"""
        logger.info("🚀 Начинаю обновление исторических данных...")
        
        season = self.get_current_season()
        logger.info(f"📅 Текущий сезон: {season}")
        
        # Загружаем старые данные
        old_df = self.load_existing_data()
        
        # Скачиваем свежие данные для всех лиг
        all_new = []
        for league_code, league_name in self.LEAGUES.items():
            logger.info(f"📥 Скачиваю {league_name}...")
            df = await self.download_latest_csv(league_code, season)
            if not df.empty:
                df["league_code"] = league_code
                df["league_name"] = league_name
                df["season"] = season
                all_new.append(df)
            await asyncio.sleep(1)
        
        if not all_new:
            logger.warning("⚠️ Не удалось скачать новые данные")
            return
        
        new_df = pd.concat(all_new, ignore_index=True)
        logger.info(f"📊 Скачано {len(new_df)} свежих матчей")
        
        # Объединяем
        merged_df = self.merge_data(old_df, new_df)
        
        # Преобразуем дату
        if "Date" in merged_df.columns:
            for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]:
                try:
                    merged_df["Date"] = pd.to_datetime(merged_df["Date"], format=fmt, errors="coerce")
                    if merged_df["Date"].notna().sum() > len(merged_df) * 0.5:
                        break
                except:
                    continue
            merged_df = merged_df.dropna(subset=["Date"])
        
        # Сохраняем
        merged_df.to_csv(self.main_file, index=False, encoding="utf-8")
        
        logger.info(f"🎉 Обновление завершено!")
        logger.info(f"📊 Итого матчей: {len(merged_df)}")
        logger.info(f"💾 Файл: {self.main_file}")


async def main():
    updater = DataUpdater()
    await updater.update()


if __name__ == "__main__":
    asyncio.run(main())
