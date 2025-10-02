"""
Timeframe Models
Timeframe-Konfigurationen und Definitionen
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TimeframeConfig:
    """
    Timeframe-Konfiguration

    Attributes:
        timeframe: Timeframe-String (z.B. "5m", "1h")
        minutes: Anzahl Minuten des Timeframes
        display_name: Anzeigename für UI
    """
    timeframe: str
    minutes: int
    display_name: str

    def to_dict(self) -> Dict[str, any]:
        """Konvertiert TimeframeConfig zu Dictionary"""
        return {
            'timeframe': self.timeframe,
            'minutes': self.minutes,
            'display_name': self.display_name
        }

    @property
    def seconds(self) -> int:
        """Timeframe in Sekunden"""
        return self.minutes * 60

    @property
    def is_intraday(self) -> bool:
        """Prüft ob Timeframe Intraday ist (< 1 Tag)"""
        return self.minutes < 1440  # 1440 = 24 * 60

    @property
    def candles_per_day(self) -> int:
        """Anzahl Kerzen pro Tag (angenähert)"""
        # Annahme: 6.5h Trading-Zeit für Futures (390 Minuten)
        trading_minutes_per_day = 390
        return max(1, trading_minutes_per_day // self.minutes)

    def __repr__(self) -> str:
        """String-Repräsentation"""
        return f"TimeframeConfig({self.timeframe}, {self.minutes}min)"


# Zentrale Timeframe-Definitionen
TIMEFRAME_CONFIGS: Dict[str, TimeframeConfig] = {
    "1m": TimeframeConfig(
        timeframe="1m",
        minutes=1,
        display_name="1 Minute"
    ),
    "2m": TimeframeConfig(
        timeframe="2m",
        minutes=2,
        display_name="2 Minutes"
    ),
    "3m": TimeframeConfig(
        timeframe="3m",
        minutes=3,
        display_name="3 Minutes"
    ),
    "5m": TimeframeConfig(
        timeframe="5m",
        minutes=5,
        display_name="5 Minutes"
    ),
    "15m": TimeframeConfig(
        timeframe="15m",
        minutes=15,
        display_name="15 Minutes"
    ),
    "30m": TimeframeConfig(
        timeframe="30m",
        minutes=30,
        display_name="30 Minutes"
    ),
    "1h": TimeframeConfig(
        timeframe="1h",
        minutes=60,
        display_name="1 Hour"
    ),
    "4h": TimeframeConfig(
        timeframe="4h",
        minutes=240,
        display_name="4 Hours"
    )
}

# Liste aller verfügbaren Timeframes
AVAILABLE_TIMEFRAMES = list(TIMEFRAME_CONFIGS.keys())


def get_timeframe_config(timeframe: str) -> TimeframeConfig:
    """
    Holt Timeframe-Konfiguration

    Args:
        timeframe: Timeframe-String (z.B. "5m")

    Returns:
        TimeframeConfig-Objekt

    Raises:
        ValueError: Wenn Timeframe nicht existiert
    """
    if timeframe not in TIMEFRAME_CONFIGS:
        raise ValueError(f"Unknown timeframe: {timeframe}. Available: {AVAILABLE_TIMEFRAMES}")
    return TIMEFRAME_CONFIGS[timeframe]


def get_timeframe_minutes(timeframe: str) -> int:
    """
    Holt Minuten für Timeframe

    Args:
        timeframe: Timeframe-String

    Returns:
        Anzahl Minuten

    Example:
        >>> get_timeframe_minutes("5m")
        5
        >>> get_timeframe_minutes("1h")
        60
    """
    config = get_timeframe_config(timeframe)
    return config.minutes


def is_valid_timeframe(timeframe: str) -> bool:
    """
    Prüft ob Timeframe gültig ist

    Args:
        timeframe: Timeframe-String

    Returns:
        True wenn gültig, sonst False
    """
    return timeframe in TIMEFRAME_CONFIGS


def get_next_higher_timeframe(timeframe: str) -> str:
    """
    Holt nächsthöheren Timeframe

    Args:
        timeframe: Aktueller Timeframe

    Returns:
        Nächsthöherer Timeframe oder aktueller wenn schon höchster

    Example:
        >>> get_next_higher_timeframe("5m")
        "15m"
    """
    current_minutes = get_timeframe_minutes(timeframe)

    # Sortiere Timeframes nach Minuten
    sorted_tfs = sorted(TIMEFRAME_CONFIGS.keys(), key=lambda tf: TIMEFRAME_CONFIGS[tf].minutes)

    # Finde nächsthöheren
    for tf in sorted_tfs:
        if TIMEFRAME_CONFIGS[tf].minutes > current_minutes:
            return tf

    # Bereits höchster Timeframe
    return timeframe


def get_next_lower_timeframe(timeframe: str) -> str:
    """
    Holt nächstniedrigeren Timeframe

    Args:
        timeframe: Aktueller Timeframe

    Returns:
        Nächstniedrigerer Timeframe oder aktueller wenn schon niedrigster
    """
    current_minutes = get_timeframe_minutes(timeframe)

    # Sortiere Timeframes nach Minuten (absteigend)
    sorted_tfs = sorted(TIMEFRAME_CONFIGS.keys(), key=lambda tf: TIMEFRAME_CONFIGS[tf].minutes, reverse=True)

    # Finde nächstniedrigeren
    for tf in sorted_tfs:
        if TIMEFRAME_CONFIGS[tf].minutes < current_minutes:
            return tf

    # Bereits niedrigster Timeframe
    return timeframe
