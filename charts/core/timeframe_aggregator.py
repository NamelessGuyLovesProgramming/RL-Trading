"""
Timeframe Aggregator
Intelligente Kerzen-Logik für verschiedene Timeframes mit incomplete candle tracking
"""

from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
import random


class TimeframeAggregator:
    """Intelligente Kerzen-Logik für verschiedene Timeframes"""

    def __init__(self):
        # Timeframe-Definitionen in Minuten
        self.timeframes: Dict[str, int] = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60
        }

        # Aktuelle unvollständige Kerzen pro Timeframe
        self.incomplete_candles: Dict[str, Dict] = {}

        # Letzte vollständige Kerze für jeden Timeframe
        self.last_complete_candles: Dict[str, Dict] = {}

    def add_minute_to_timeframe(self, current_time: datetime, timeframe: str, last_candle: dict) -> Tuple[Optional[dict], Optional[dict], bool]:
        """
        Fügt eine Minute zu einem Timeframe hinzu und gibt zurück:
        - neue_kerze: dict mit neuer Kerze oder None
        - incomplete_data: dict mit unvollständiger Kerze oder None
        - is_complete: bool ob Kerze vollständig ist
        """
        tf_minutes = self.timeframes.get(timeframe, 1)
        new_time = current_time + timedelta(minutes=1)

        # Berechne Start-Zeit für aktuelle Timeframe-Periode
        if timeframe == '1m':
            period_start = new_time.replace(second=0, microsecond=0)
        elif timeframe == '5m':
            period_start = new_time.replace(minute=(new_time.minute // 5) * 5, second=0, microsecond=0)
        elif timeframe == '15m':
            period_start = new_time.replace(minute=(new_time.minute // 15) * 15, second=0, microsecond=0)
        elif timeframe == '30m':
            period_start = new_time.replace(minute=(new_time.minute // 30) * 30, second=0, microsecond=0)
        elif timeframe == '1h':
            period_start = new_time.replace(minute=0, second=0, microsecond=0)
        else:
            period_start = new_time.replace(second=0, microsecond=0)

        # Generiere Mock-Preis-Bewegung basierend auf letzter Kerze
        last_close = last_candle.get('close', 18500)
        price_change = random.uniform(-20, 20)  # ±20 Punkte Bewegung
        new_price = last_close + price_change

        # Prüfe ob wir eine neue Periode beginnen
        key = f"{timeframe}_{period_start.isoformat()}"

        if key not in self.incomplete_candles:
            # Neue Periode beginnt
            self.incomplete_candles[key] = {
                'time': int(period_start.timestamp()),
                'open': new_price,
                'high': new_price,
                'low': new_price,
                'close': new_price,
                'period_start': period_start,
                'minutes_elapsed': 1,
                'timeframe': timeframe,
                'is_complete': False
            }
        else:
            # Bestehende Periode fortsetzen
            candle = self.incomplete_candles[key]
            candle['high'] = max(candle['high'], new_price)
            candle['low'] = min(candle['low'], new_price)
            candle['close'] = new_price
            candle['minutes_elapsed'] += 1

        current_candle = self.incomplete_candles[key]

        # Prüfe ob Periode vollständig ist
        if current_candle['minutes_elapsed'] >= tf_minutes:
            # Kerze ist vollständig
            complete_candle = current_candle.copy()
            complete_candle['is_complete'] = True

            # Entferne aus incomplete und speichere als last_complete
            del self.incomplete_candles[key]
            self.last_complete_candles[timeframe] = complete_candle

            return complete_candle, None, True
        else:
            # Kerze ist noch unvollständig
            return None, current_candle, False

    def get_incomplete_candle(self, timeframe: str) -> Optional[dict]:
        """Gibt die aktuelle unvollständige Kerze für einen Timeframe zurück"""
        for key, candle in self.incomplete_candles.items():
            if candle['timeframe'] == timeframe:
                return candle
        return None

    def get_all_incomplete_candles(self) -> Dict[str, list]:
        """Gibt alle unvollständigen Kerzen zurück, gruppiert nach Timeframe"""
        result: Dict[str, list] = {}
        for key, candle in self.incomplete_candles.items():
            tf = candle['timeframe']
            if tf not in result:
                result[tf] = []
            result[tf].append(candle)
        return result
