    def _train_on_railway(self):
        """Обучает модель на Railway если данных достаточно"""
        # Пробуем разные пути к данным
        possible_paths = [
            "data/historical/football_data_matches.csv",
            "data/football_data_matches.csv",
            "/app/data/historical/football_data_matches.csv",
            "/app/data/football_data_matches.csv"
        ]
        
        data_path = None
        for path in possible_paths:
            if os.path.exists(path):
                data_path = path
                logger.info(f"✅ Найдены данные: {path}")
                break
        
        if not data_path:
            logger.error("❌ Данные не найдены ни в одном из путей")
            # Покажем, что реально есть в папке
            for root, dirs, files in os.walk("data"):
                for f in files:
                    if "football" in f.lower():
                        logger.info(f"   Найден файл: {os.path.join(root, f)}")
            return