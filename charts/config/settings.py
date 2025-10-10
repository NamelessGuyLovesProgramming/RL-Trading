"""
Application Settings - Pydantic Settings Management
REFACTOR PHASE 6: Zentralisierte Konfiguration mit Environment Variables
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application Settings mit Environment Variable Support

    Alle Settings können via .env Datei überschrieben werden:
    - HOST=0.0.0.0
    - PORT=8003
    - DATA_PATH=src/data/aggregated
    - etc.
    """

    # ============================================================
    # SERVER CONFIGURATION
    # ============================================================
    host: str = "0.0.0.0"
    port: int = 8003
    reload: bool = False
    log_level: str = "info"

    # ============================================================
    # DATA CONFIGURATION
    # ============================================================
    data_path: str = "src/data/aggregated"
    default_symbol: str = "NQ=F"
    default_timeframe: str = "5m"

    # CSV-Pfade
    csv_base_path: str = "src/data/aggregated"
    csv_file_pattern: str = "{symbol}-{year}.csv"

    # ============================================================
    # CACHE CONFIGURATION
    # ============================================================
    cache_size_mb: int = 100
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600  # 1 Stunde

    # ============================================================
    # CHART CONFIGURATION
    # ============================================================
    default_candle_count: int = 300
    max_visible_candles: int = 2000
    min_visible_candles: int = 10

    # ============================================================
    # WEBSOCKET CONFIGURATION
    # ============================================================
    ws_heartbeat_interval: int = 30
    ws_timeout: int = 300
    ws_max_connections: int = 100

    # ============================================================
    # DEBUG CONFIGURATION
    # ============================================================
    debug_mode: bool = False
    debug_log_sql: bool = False
    debug_log_cache: bool = False

    # ============================================================
    # PERFORMANCE CONFIGURATION
    # ============================================================
    enable_preloading: bool = True
    preload_adjacent_timeframes: bool = True
    async_data_loading: bool = True

    # ============================================================
    # TRADING CONFIGURATION
    # ============================================================
    max_positions: int = 10
    default_leverage: float = 1.0

    class Config:
        """Pydantic Config"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

        # Allow extra fields (for backwards compatibility)
        extra = "ignore"


# ============================================================
# SINGLETON INSTANCE
# ============================================================
settings = Settings()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_csv_path(symbol: str, timeframe: str, year: int) -> str:
    """
    Generiert CSV-Pfad für Symbol, Timeframe und Jahr

    Args:
        symbol: Trading-Symbol (z.B. "nq")
        timeframe: Timeframe (z.B. "5m")
        year: Jahr (z.B. 2024)

    Returns:
        Vollständiger Pfad zur CSV-Datei

    Example:
        >>> get_csv_path("nq", "5m", 2024)
        'src/data/aggregated/5m/nq-2024.csv'
    """
    return os.path.join(
        settings.csv_base_path,
        timeframe,
        f"{symbol.lower()}-{year}.csv"
    )


def validate_timeframe(timeframe: str) -> bool:
    """
    Validiert ob Timeframe unterstützt wird

    Args:
        timeframe: Timeframe-String (z.B. "5m")

    Returns:
        True wenn gültig, False sonst
    """
    from .constants import TIMEFRAMES
    return timeframe in TIMEFRAMES


def get_env_info() -> dict:
    """
    Gibt aktuelle Environment-Info zurück

    Returns:
        Dict mit Environment-Variablen und Settings
    """
    return {
        "host": settings.host,
        "port": settings.port,
        "data_path": settings.data_path,
        "cache_enabled": settings.enable_cache,
        "debug_mode": settings.debug_mode,
        "env_file_loaded": os.path.exists(".env")
    }


# ============================================================
# DEVELOPMENT HELPERS
# ============================================================

if __name__ == "__main__":
    # Quick Settings Test
    print("=" * 60)
    print("📋 RL Trading Chart Server - Settings")
    print("=" * 60)
    print(f"🌐 Server: {settings.host}:{settings.port}")
    print(f"📂 Data Path: {settings.data_path}")
    print(f"📊 Default: {settings.default_symbol} @ {settings.default_timeframe}")
    print(f"💾 Cache: {'Enabled' if settings.enable_cache else 'Disabled'} ({settings.cache_size_mb}MB)")
    print(f"🐛 Debug: {'ON' if settings.debug_mode else 'OFF'}")
    print(f"🔧 Environment File: {'.env' if os.path.exists('.env') else 'Not found'}")
    print("=" * 60)

    # Test CSV Path Generation
    print("\n📁 CSV Path Examples:")
    for tf in ["1m", "5m", "1h"]:
        print(f"  {tf}: {get_csv_path('nq', tf, 2024)}")
