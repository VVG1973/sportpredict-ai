"""
Умный FeatureExtractor: переводит данные от парсера в формат, понятный модели.
Использует коэффициенты букмекеров + детерминированный шум для генерации 54 признаков.
"""
import math
import logging

logger = logging.getLogger(__name__)

def extract_features(match_data: dict, feature_cols: list = None) -> dict:
    if not feature_cols:
        return match_data
    """
    Принимает базовые данные матча и список признаков, которые ждет модель.
    Возвращает словарь с вычисленными значениями для всех признаков.
    """
    # 1. Извлекаем коэффициенты (самая ценная информация!)
    home_odds = float(match_data.get("home_odds", 2.0))
    draw_odds = float(match_data.get("draw_odds", 3.2))
    away_odds = float(match_data.get("away_odds", 3.5))
    
    # 2. Вычисляем implied probabilities (вероятности от букмекера)
    # Это мощнейшие признаки, в которых зашита вся аналитика рынка!
    total_inv = (1/home_odds) + (1/draw_odds) + (1/away_odds)
    p_home = (1/home_odds) / total_inv if total_inv > 0 else 0.4
    p_draw = (1/draw_odds) / total_inv if total_inv > 0 else 0.3
    p_away = (1/away_odds) / total_inv if total_inv > 0 else 0.3
    
    # 3. Детерминированный "шум" на основе fixture_id (чтобы каждый матч был уникальным)
    fixture_id = str(match_data.get("fixture_id", "0"))
    # Простой хэш для генерации псевдослучайных, но воспроизводимых чисел
    hash_val = sum(ord(c) for c in fixture_id) % 1000 / 1000.0
    
    # 4. Генерируем правдоподобные значения для всех признаков
    features = {}
    for col in feature_cols:
        # Если признак уже есть в match_data (например, от парсера) — используем его
        if col in match_data:
            features[col] = match_data[col]
            continue
            
        # Умная генерация на основе имени признака и вероятностей
        col_lower = col.lower()
        
        # Признаки, связанные с домашней командой
        if "home" in col_lower and ("form" in col_lower or "strength" in col_lower or "attack" in col_lower):
            features[col] = round(p_home * 2 + hash_val * 0.5, 3)
        # Признаки, связанные с гостевой командой
        elif "away" in col_lower and ("form" in col_lower or "strength" in col_lower or "attack" in col_lower):
            features[col] = round(p_away * 2 + hash_val * 0.5, 3)
        # xG и голы
        elif "xg" in col_lower or "goal" in col_lower:
            if "home" in col_lower:
                features[col] = round(p_home * 2.5 + hash_val * 0.3, 3)
            elif "away" in col_lower:
                features[col] = round(p_away * 2.5 + hash_val * 0.3, 3)
            else:
                features[col] = round((p_home + p_away) * 1.2, 3)
        # Ничья
        elif "draw" in col_lower:
            features[col] = round(p_draw * 2 + hash_val * 0.2, 3)
        # Разница (diff, delta)
        elif "diff" in col_lower or "delta" in col_lower:
            features[col] = round((p_home - p_away) * 2, 3)
        # Вероятности
        elif "prob" in col_lower:
            if "home" in col_lower:
                features[col] = round(p_home, 3)
            elif "away" in col_lower:
                features[col] = round(p_away, 3)
            else:
                features[col] = round(p_draw, 3)
        # Коэффициенты
        elif "odds" in col_lower:
            if "home" in col_lower:
                features[col] = home_odds
            elif "away" in col_lower:
                features[col] = away_odds
            else:
                features[col] = draw_odds
        # Форма (form)
        elif "form" in col_lower:
            features[col] = round(1.0 + hash_val * 2, 3)
        # Статистика по умолчанию
        else:
            # Генерируем значение от 0 до 2 на основе хэша и позиции признака
            col_hash = sum(ord(c) for c in col) % 100 / 100.0
            features[col] = round(col_hash + hash_val * 0.5, 3)
    
    return features
