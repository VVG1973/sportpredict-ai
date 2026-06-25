import logging
import httpx
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


class HistoricalDataCollector:
    """Сборщик исторических данных с football-data.org"""
    
    BASE_URL = "https://www.football-data.co.uk/mmz4281"
    
    LEAGUES = {
        "E0": "English Premier League",
        "E1": "English Championship",
        "SP1": "Spanish La Liga",
        "I1": "Italian Serie A",
        "D1": "German Bundesliga",
        "F1": "French Ligue 1",
        "N1": "Dutch Eredivisie",
        "P1": "Portuguese Primeira Liga",
        "B1": "Belgian First Division",
        "T1": "Turkish Super Lig",
    }
    
    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def download_season(self, league_code: str, season: str) -> pd.DataFrame:
        """Скачивает данные за один сезон одной лиги"""
        url = f"{self.BASE_URL}/{season}/{league_code}.csv"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # 🆕 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: работаем с бинарными данными
                csv_path = self.data_dir / f"{league_code}_{season}.csv"
                csv_path.write_bytes(response.content)  # ✅ write_bytes вместо write_text
                
                # 🆕 Читаем с encoding='utf-8-sig' (автоматически удаляет BOM)
                df = pd.read_csv(csv_path, encoding='utf-8-sig')
                logger.info(f"✅ Скачано {len(df)} матчей: {league_code} {season}")
                
                return df
        except Exception as e:
            logger.warning(f"⚠️ Не удалось скачать {league_code} {season}: {e}")
            return pd.DataFrame()
    
    async def collect_all_data(self, seasons: List[str] = None) -> pd.DataFrame:
        """Собирает данные за несколько сезонов всех лиг"""
        if seasons is None:
            seasons = ["2324", "2223", "2122", "2021", "1920"]
        
        all_data = []
        
        for season in seasons:
            for league_code, league_name in self.LEAGUES.items():
                logger.info(f"📥 Скачиваю {league_name} {season}...")
                df = await self.download_season(league_code, season)
                
                if not df.empty:
                    df["league_code"] = league_code
                    df["league_name"] = league_name
                    df["season"] = season
                    all_data.append(df)
                
                import asyncio
                await asyncio.sleep(0.5)
        
        if not all_data:
            logger.error("❌ Не удалось собрать данные")
            return pd.DataFrame()
        
        combined_df = pd.concat(all_data, ignore_index=True)
        
        output_path = self.data_dir / "all_matches.csv"
        combined_df.to_csv(output_path, index=False, encoding='utf-8')
        
        logger.info(f"✅ Собрано {len(combined_df)} матчей из {len(all_data)} файлов")
        logger.info(f"💾 Сохранено в {output_path}")
        
        return combined_df
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Очищает и стандартизирует данные"""
        critical_cols = ["HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
        df = df.dropna(subset=critical_cols)
        
        if "Date" in df.columns:
            # Пробуем несколько форматов дат
            for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]:
                try:
                    df["Date"] = pd.to_datetime(df["Date"], format=fmt, errors="coerce")
                    if df["Date"].notna().sum() > len(df) * 0.5:
                        break
                except:
                    continue
            df = df.dropna(subset=["Date"])
        
        df = df.drop_duplicates()
        
        logger.info(f"✅ После очистки: {len(df)} матчей")
        return df


async def main():
    """Запускает сбор исторических данных"""
    collector = HistoricalDataCollector()
    
    logger.info("🚀 Начинаю сбор исторических данных...")
    logger.info("⏳ Это займёт 5-10 минут...")
    
    df = await collector.collect_all_data(seasons=["2324", "2223", "2122", "2021", "1920"])
    
    if not df.empty:
        df_clean = collector.clean_data(df)
        
        clean_path = Path("data/historical/all_matches_clean.csv")
        df_clean.to_csv(clean_path, index=False, encoding='utf-8')
        
        logger.info(f"🎉 Готово! {len(df_clean)} матчей сохранено в {clean_path}")
        logger.info(f"📊 Лиги: {df_clean['league_name'].nunique()}")
        logger.info(f"📅 Период: {df_clean['Date'].min()} - {df_clean['Date'].max()}")
    else:
        logger.error("❌ Не удалось собрать данные")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
