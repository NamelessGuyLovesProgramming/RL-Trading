"""
Configuration Package - Settings & Constants
REFACTOR PHASE 6: Zentralisierte Konfiguration
"""

from .settings import settings
from .constants import (
    TIMEFRAMES,
    TIMEFRAME_MINUTES,
    DEFAULT_CANDLE_COUNT,
    MAX_VISIBLE_CANDLES,
    WS_HEARTBEAT_INTERVAL,
    WS_TIMEOUT
)

__all__ = [
    'settings',
    'TIMEFRAMES',
    'TIMEFRAME_MINUTES',
    'DEFAULT_CANDLE_COUNT',
    'MAX_VISIBLE_CANDLES',
    'WS_HEARTBEAT_INTERVAL',
    'WS_TIMEOUT'
]
