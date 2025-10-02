"""
Chart Data Models
Kerzen-Daten und Chart-Datenstrukturen
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd


@dataclass
class Candle:
    """
    Einzelne Chart-Kerze (OHLC)

    Attributes:
        time: Unix Timestamp (Sekunden)
        open: Eröffnungspreis
        high: Höchstpreis
        low: Tiefstpreis
        close: Schlusspreis
        volume: Handelsvolumen (optional)
    """
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Kerze zu Dictionary für JSON-Serialisierung"""
        return {
            'time': self.time,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }

    @property
    def datetime(self) -> datetime:
        """Konvertiert Unix Timestamp zu datetime-Objekt"""
        return datetime.fromtimestamp(self.time)


@dataclass
class ChartData:
    """
    Chart-Daten Container

    Attributes:
        candles: Liste von Kerzen
        timeframe: Timeframe-String (z.B. "5m", "1h")
        symbol: Trading-Symbol (z.B. "NQ=F")
        metadata: Zusätzliche Metadaten (optional)
    """
    candles: List[Candle]
    timeframe: str
    symbol: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert ChartData zu Dictionary für JSON-Serialisierung"""
        return {
            'candles': [candle.to_dict() for candle in self.candles],
            'timeframe': self.timeframe,
            'symbol': self.symbol,
            'metadata': self.metadata
        }

    @property
    def candle_count(self) -> int:
        """Anzahl der Kerzen"""
        return len(self.candles)

    @property
    def first_candle(self) -> Optional[Candle]:
        """Erste Kerze im Dataset"""
        return self.candles[0] if self.candles else None

    @property
    def last_candle(self) -> Optional[Candle]:
        """Letzte Kerze im Dataset"""
        return self.candles[-1] if self.candles else None


class CandleFactory:
    """
    Factory für Kerzen-Erstellung aus verschiedenen Quellen
    """

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Candle:
        """
        Erstellt Kerze aus Dictionary

        Args:
            data: Dictionary mit Kerzen-Daten

        Returns:
            Candle-Objekt

        Example:
            >>> data = {'time': 1234567890, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5}
            >>> candle = CandleFactory.from_dict(data)
        """
        return Candle(
            time=int(data['time']),
            open=float(data['open']),
            high=float(data['high']),
            low=float(data['low']),
            close=float(data['close']),
            volume=float(data['volume']) if 'volume' in data and data['volume'] is not None else None
        )

    @staticmethod
    def from_csv_row(row: pd.Series) -> Candle:
        """
        Erstellt Kerze aus Pandas Series (CSV-Zeile)

        Args:
            row: Pandas Series mit Kerzen-Daten

        Returns:
            Candle-Objekt

        Example:
            >>> df = pd.read_csv('candles.csv')
            >>> candle = CandleFactory.from_csv_row(df.iloc[0])
        """
        # Zeit-Handling: Unix Timestamp oder datetime
        if isinstance(row['time'], pd.Timestamp):
            time_val = int(row['time'].timestamp())
        elif isinstance(row['time'], (int, float)):
            time_val = int(row['time'])
        else:
            # Fallback: Parse als datetime string
            time_val = int(pd.Timestamp(row['time']).timestamp())

        return Candle(
            time=time_val,
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume']) if 'volume' in row.index and pd.notna(row['volume']) else None
        )

    @staticmethod
    def from_dataframe_row(row: pd.Series) -> Candle:
        """
        Erstellt Kerze aus Pandas DataFrame Row (flexible Spalten-Namen)
        Unterstützt sowohl uppercase (Open, High, Low, Close) als auch lowercase

        Args:
            row: Pandas Series mit Kerzen-Daten

        Returns:
            Candle-Objekt
        """
        # Flexible Spalten-Namen (uppercase oder lowercase)
        def get_column_value(row, *possible_names):
            for name in possible_names:
                if name in row.index:
                    return row[name]
            raise KeyError(f"Keine der Spalten {possible_names} gefunden")

        # Zeit-Handling
        time_val = get_column_value(row, 'time', 'Time')
        if isinstance(time_val, pd.Timestamp):
            time_val = int(time_val.timestamp())
        elif not isinstance(time_val, (int, float)):
            time_val = int(pd.Timestamp(time_val).timestamp())
        else:
            time_val = int(time_val)

        # OHLC Werte (flexible Spalten-Namen)
        open_val = float(get_column_value(row, 'open', 'Open'))
        high_val = float(get_column_value(row, 'high', 'High'))
        low_val = float(get_column_value(row, 'low', 'Low'))
        close_val = float(get_column_value(row, 'close', 'Close'))

        # Volume (optional)
        volume_val = None
        try:
            vol = get_column_value(row, 'volume', 'Volume')
            if pd.notna(vol):
                volume_val = float(vol)
        except KeyError:
            pass

        return Candle(
            time=time_val,
            open=open_val,
            high=high_val,
            low=low_val,
            close=close_val,
            volume=volume_val
        )

    @staticmethod
    def from_list(candles_data: List[Dict[str, Any]]) -> List[Candle]:
        """
        Erstellt Liste von Kerzen aus Liste von Dictionaries

        Args:
            candles_data: Liste von Dictionaries mit Kerzen-Daten

        Returns:
            Liste von Candle-Objekten
        """
        return [CandleFactory.from_dict(data) for data in candles_data]

    @staticmethod
    def to_lightweight_charts_format(candles: List[Candle]) -> List[Dict[str, Any]]:
        """
        Konvertiert Kerzen zu Lightweight Charts Format

        Args:
            candles: Liste von Kerzen

        Returns:
            Liste von Dictionaries im Lightweight Charts Format
        """
        return [candle.to_dict() for candle in candles]
