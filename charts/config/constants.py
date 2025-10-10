"""
Application Constants - Timeframes, Limits, Defaults
REFACTOR PHASE 6: Zentralisierte Konstanten
"""

from typing import Dict, List

# ============================================================
# TIMEFRAME DEFINITIONS
# ============================================================

TIMEFRAMES: List[str] = [
    "1m",   # 1 Minute
    "2m",   # 2 Minutes
    "3m",   # 3 Minutes
    "5m",   # 5 Minutes
    "15m",  # 15 Minutes
    "30m",  # 30 Minutes
    "1h",   # 1 Hour
    "4h"    # 4 Hours
]

TIMEFRAME_MINUTES: Dict[str, int] = {
    "1m": 1,
    "2m": 2,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240
}

TIMEFRAME_DISPLAY_NAMES: Dict[str, str] = {
    "1m": "1 Minute",
    "2m": "2 Minutes",
    "3m": "3 Minutes",
    "5m": "5 Minutes",
    "15m": "15 Minutes",
    "30m": "30 Minutes",
    "1h": "1 Hour",
    "4h": "4 Hours"
}

# Timeframe-Hierarchie (für Smart-Preloading)
TIMEFRAME_HIERARCHY: Dict[str, dict] = {
    "1m": {"lower": None, "higher": "2m"},
    "2m": {"lower": "1m", "higher": "3m"},
    "3m": {"lower": "2m", "higher": "5m"},
    "5m": {"lower": "3m", "higher": "15m"},
    "15m": {"lower": "5m", "higher": "30m"},
    "30m": {"lower": "15m", "higher": "1h"},
    "1h": {"lower": "30m", "higher": "4h"},
    "4h": {"lower": "1h", "higher": None}
}


# ============================================================
# CHART CONFIGURATION
# ============================================================

# Kerzen-Limits
DEFAULT_CANDLE_COUNT: int = 300
MAX_VISIBLE_CANDLES: int = 2000
MIN_VISIBLE_CANDLES: int = 10

# Performance-Limits
MAX_PRELOAD_CANDLES: int = 5000
CACHE_WARMING_CANDLES: int = 1000


# ============================================================
# WEBSOCKET CONFIGURATION
# ============================================================

# Heartbeat & Timeouts
WS_HEARTBEAT_INTERVAL: int = 30  # Sekunden
WS_TIMEOUT: int = 300  # Sekunden (5 Minuten)
WS_MAX_MESSAGE_SIZE: int = 10 * 1024 * 1024  # 10 MB

# Connection Limits
WS_MAX_CONNECTIONS: int = 100
WS_CONNECTION_TIMEOUT: int = 10  # Sekunden


# ============================================================
# CACHE CONFIGURATION
# ============================================================

# Cache-Größen
CACHE_SIZE_MB: int = 100
CACHE_TTL_SECONDS: int = 3600  # 1 Stunde

# Cache-Keys
CACHE_KEY_CHART_DATA: str = "chart_data:{symbol}:{timeframe}:{date}"
CACHE_KEY_TIMEFRAME_INFO: str = "timeframe_info:{timeframe}"
CACHE_KEY_DEBUG_STATE: str = "debug_state"


# ============================================================
# DEBUG CONFIGURATION
# ============================================================

# Debug-Modi
DEBUG_MODE_OFF: str = "off"
DEBUG_MODE_REPLAY: str = "replay"
DEBUG_MODE_BACKTEST: str = "backtest"

# Debug-Speed Limits
DEBUG_MIN_SPEED: float = 0.1
DEBUG_MAX_SPEED: float = 100.0
DEBUG_DEFAULT_SPEED: float = 1.0


# ============================================================
# DATA VALIDATION
# ============================================================

# OHLC Validation
OHLC_EPSILON: float = 0.0001  # Toleranz für Float-Vergleiche
MIN_PRICE_VALUE: float = 0.0
MAX_PRICE_VALUE: float = 1_000_000.0

# Timestamp Validation
MIN_TIMESTAMP: int = 946684800  # 2000-01-01 00:00:00
MAX_TIMESTAMP: int = 2147483647  # 2038-01-19 03:14:07 (Y2038 Problem)


# ============================================================
# POSITION MANAGEMENT
# ============================================================

# Position Limits
MAX_POSITIONS: int = 10
MIN_POSITION_SIZE: float = 0.01
MAX_POSITION_SIZE: float = 100.0

# Position-Typen
POSITION_TYPE_LONG: str = "long"
POSITION_TYPE_SHORT: str = "short"

# Position-Status
POSITION_STATUS_OPEN: str = "open"
POSITION_STATUS_CLOSED: str = "closed"
POSITION_STATUS_PENDING: str = "pending"


# ============================================================
# API CONFIGURATION
# ============================================================

# API-Versionen
API_VERSION: str = "2.0.0"
API_TITLE: str = "RL Trading Chart Server"
API_DESCRIPTION: str = """
**Real-Time Trading Chart Server** mit WebSocket-Support

Features:
- Multi-Timeframe Charts (1m bis 4h)
- Real-Time WebSocket Updates
- Debug-Modus für Backtesting
- Position-Management
- Skip-Navigation
"""

# API-Endpunkte
API_PREFIX: str = "/api"
WS_ENDPOINT: str = "/ws"
DOCS_ENDPOINT: str = "/docs"
REDOC_ENDPOINT: str = "/redoc"


# ============================================================
# ERROR MESSAGES
# ============================================================

ERROR_MESSAGES: Dict[str, str] = {
    "invalid_timeframe": "Ungültiger Timeframe. Erlaubt: {timeframes}",
    "invalid_date": "Ungültiges Datum-Format. Erwartet: YYYY-MM-DD",
    "no_data": "Keine Daten für {symbol} @ {timeframe} verfügbar",
    "candle_count_exceeded": "Maximale Kerzen-Anzahl überschritten: {max}",
    "cache_error": "Cache-Fehler: {error}",
    "websocket_error": "WebSocket-Fehler: {error}",
    "position_limit": "Maximale Positions-Anzahl erreicht: {max}",
    "invalid_price": "Ungültiger Preis: {price}"
}


# ============================================================
# SUCCESS MESSAGES
# ============================================================

SUCCESS_MESSAGES: Dict[str, str] = {
    "timeframe_changed": "Timeframe gewechselt: {old} → {new}",
    "data_loaded": "{count} Kerzen geladen für {timeframe}",
    "cache_hit": "Cache-Hit: {key}",
    "position_created": "Position erstellt: {position_id}",
    "position_closed": "Position geschlossen: {position_id}"
}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_adjacent_timeframes(timeframe: str) -> List[str]:
    """
    Gibt benachbarte Timeframes zurück (für Preloading)

    Args:
        timeframe: Aktueller Timeframe

    Returns:
        Liste mit benachbarten Timeframes

    Example:
        >>> get_adjacent_timeframes("5m")
        ['3m', '15m']
    """
    if timeframe not in TIMEFRAME_HIERARCHY:
        return []

    adjacent = []
    lower = TIMEFRAME_HIERARCHY[timeframe]["lower"]
    higher = TIMEFRAME_HIERARCHY[timeframe]["higher"]

    if lower:
        adjacent.append(lower)
    if higher:
        adjacent.append(higher)

    return adjacent


def get_timeframe_display_name(timeframe: str) -> str:
    """
    Gibt Display-Name für Timeframe zurück

    Args:
        timeframe: Timeframe (z.B. "5m")

    Returns:
        Display-Name (z.B. "5 Minutes")
    """
    return TIMEFRAME_DISPLAY_NAMES.get(timeframe, timeframe)


def is_valid_timeframe(timeframe: str) -> bool:
    """
    Prüft ob Timeframe gültig ist

    Args:
        timeframe: Zu prüfender Timeframe

    Returns:
        True wenn gültig, False sonst
    """
    return timeframe in TIMEFRAMES


def get_timeframe_minutes(timeframe: str) -> int:
    """
    Gibt Minuten-Wert für Timeframe zurück

    Args:
        timeframe: Timeframe (z.B. "5m")

    Returns:
        Anzahl Minuten

    Example:
        >>> get_timeframe_minutes("5m")
        5
    """
    return TIMEFRAME_MINUTES.get(timeframe, 0)


# ============================================================
# DEVELOPMENT HELPERS
# ============================================================

if __name__ == "__main__":
    # Quick Constants Test
    print("=" * 60)
    print("📊 RL Trading Chart Server - Constants")
    print("=" * 60)
    print(f"⏱️  Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"📈 Default Candles: {DEFAULT_CANDLE_COUNT}")
    print(f"🔌 WebSocket Timeout: {WS_TIMEOUT}s")
    print(f"💾 Cache TTL: {CACHE_TTL_SECONDS}s")
    print("=" * 60)

    # Test Adjacent Timeframes
    print("\n🔗 Adjacent Timeframes:")
    for tf in TIMEFRAMES:
        adjacent = get_adjacent_timeframes(tf)
        print(f"  {tf}: {adjacent}")

    # Test Display Names
    print("\n📝 Display Names:")
    for tf in TIMEFRAMES:
        print(f"  {tf} → {get_timeframe_display_name(tf)}")
