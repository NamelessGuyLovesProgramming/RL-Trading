"""
Cache Repository - Caching Layer für Chart-Daten
Wrapper für HighPerformanceChartCache mit vereinfachter API
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from charts.models.chart_data import Candle, CandleFactory


class CacheRepository:
    """
    Repository für Cache-basierten Datenzugriff

    Verantwortlichkeiten:
    - Wrapper für HighPerformanceChartCache
    - Unified API für Cache-Operationen
    - Performance-Optimierung durch intelligentes Caching
    - LRU Cache Management
    """

    def __init__(self, cache_size_mb: int = 100):
        """
        Initialisiert Cache Repository

        Args:
            cache_size_mb: Maximale Cache-Größe in MB
        """
        self._cache = None  # Lazy initialization
        self._cache_size_mb = cache_size_mb
        self._initialized = False
        print(f"[CacheRepository] Initialisiert mit cache_size: {cache_size_mb}MB")

    def initialize(self, csv_path: Optional[str] = None, max_rows: Optional[int] = 50000) -> bool:
        """
        Initialisiert HighPerformanceChartCache

        Args:
            csv_path: Pfad zur Master 1m CSV (optional, auto-detect)
            max_rows: Maximale Zeilen für Performance

        Returns:
            True wenn erfolgreich initialisiert
        """
        try:
            from src.performance.high_performance_cache import HighPerformanceChartCache

            self._cache = HighPerformanceChartCache(cache_size_mb=self._cache_size_mb)
            success = self._cache.load_master_dataset(csv_path=csv_path, max_rows=max_rows)

            if success:
                self._initialized = True
                print("[CacheRepository] HighPerformanceChartCache erfolgreich initialisiert")
            else:
                print("[CacheRepository] Fehler beim Laden des Master Datasets")

            return success

        except ImportError:
            print("[CacheRepository] HighPerformanceChartCache nicht verfügbar - Fallback zu No-Cache Mode")
            self._cache = None
            self._initialized = False
            return False
        except Exception as e:
            print(f"[CacheRepository] Fehler bei Initialisierung: {e}")
            self._cache = None
            self._initialized = False
            return False

    def is_initialized(self) -> bool:
        """Prüft ob Cache initialisiert ist"""
        return self._initialized and self._cache is not None

    def get_candles(
        self,
        timeframe: str,
        target_date: datetime,
        count: int = 200
    ) -> Optional[List[Candle]]:
        """
        Holt Kerzen aus Cache

        Args:
            timeframe: Timeframe (z.B. "5m")
            target_date: Start-Datum
            count: Anzahl Kerzen

        Returns:
            Liste von Candles oder None bei Cache-Miss
        """
        if not self.is_initialized():
            return None

        try:
            # Target date als String formatieren
            date_str = target_date.strftime('%Y-%m-%d')

            # Daten aus Cache holen
            result = self._cache.get_timeframe_data(
                timeframe=timeframe,
                target_date=date_str,
                candle_count=count
            )

            if not result or 'data' not in result:
                return None

            # Konvertiere zu Candle-Objekten
            candles = []
            for candle_dict in result['data']:
                candle = CandleFactory.from_dict(candle_dict)
                candles.append(candle)

            # Performance-Stats loggen
            if 'performance_stats' in result:
                stats = result['performance_stats']
                cache_hit = stats.get('cache_hit', False)
                response_time = stats.get('response_time_ms', 0)
                print(f"[CacheRepository] {'Cache-HIT' if cache_hit else 'Cache-MISS'}: "
                      f"{len(candles)} candles in {response_time:.1f}ms")

            return candles

        except Exception as e:
            print(f"[CacheRepository] Fehler beim Laden aus Cache: {e}")
            return None

    def store_candles(self, timeframe: str, candles: List[Candle]):
        """
        Speichert Kerzen in Cache (falls unterstützt)

        Note: HighPerformanceChartCache managed Caching automatisch,
        diese Methode ist für zukünftige Erweiterungen

        Args:
            timeframe: Timeframe
            candles: Liste von Candles
        """
        # HighPerformanceChartCache managed Caching intern
        # Diese Methode ist für Kompatibilität mit anderen Cache-Implementierungen
        pass

    def invalidate(self, timeframe: Optional[str] = None):
        """
        Invalidiert Cache (komplett oder für spezifischen Timeframe)

        Args:
            timeframe: Spezifischer Timeframe oder None für kompletten Cache
        """
        if not self.is_initialized():
            return

        if timeframe is None:
            # Kompletten Cache leeren
            self._cache.clear_cache()
            print("[CacheRepository] Cache komplett invalidiert")
        else:
            # HighPerformanceChartCache unterstützt keine partielle Invalidierung
            # Für zukünftige Implementierungen vorgesehen
            print(f"[CacheRepository] Partielle Invalidierung für {timeframe} nicht unterstützt")

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Holt Performance-Statistiken vom Cache

        Returns:
            Dictionary mit Performance-Stats
        """
        if not self.is_initialized():
            return {
                'initialized': False,
                'error': 'Cache not initialized'
            }

        try:
            stats = self._cache.get_performance_stats()
            return {
                'initialized': True,
                **stats
            }
        except Exception as e:
            return {
                'initialized': True,
                'error': str(e)
            }

    def preload_timeframe(self, timeframe: str, target_date: datetime, count: int = 200):
        """
        Preloaded einen Timeframe für schnelleren Zugriff

        Args:
            timeframe: Timeframe
            target_date: Datum
            count: Anzahl Kerzen
        """
        if not self.is_initialized():
            return

        # Stiller Preload - Fehler werden ignoriert
        try:
            self.get_candles(timeframe, target_date, count)
        except:
            pass


class SimpleCacheRepository:
    """
    Einfache In-Memory Cache Implementierung als Fallback

    Verwendet wenn HighPerformanceChartCache nicht verfügbar ist
    """

    def __init__(self):
        """Initialisiert einfachen Memory-Cache"""
        self._cache: Dict[str, List[Candle]] = {}
        self._max_entries = 50
        print("[SimpleCacheRepository] Fallback-Cache initialisiert")

    def get_candles(
        self,
        timeframe: str,
        target_date: datetime,
        count: int = 200
    ) -> Optional[List[Candle]]:
        """
        Holt Kerzen aus Simple-Cache

        Args:
            timeframe: Timeframe
            target_date: Start-Datum
            count: Anzahl Kerzen

        Returns:
            Liste von Candles oder None
        """
        cache_key = f"{timeframe}_{target_date.strftime('%Y-%m-%d')}_{count}"

        if cache_key in self._cache:
            print(f"[SimpleCacheRepository] Cache-HIT für {cache_key}")
            return self._cache[cache_key]

        return None

    def store_candles(
        self,
        timeframe: str,
        target_date: datetime,
        candles: List[Candle],
        count: int = 200
    ):
        """
        Speichert Kerzen in Simple-Cache

        Args:
            timeframe: Timeframe
            target_date: Start-Datum
            candles: Liste von Candles
            count: Anzahl Kerzen
        """
        cache_key = f"{timeframe}_{target_date.strftime('%Y-%m-%d')}_{count}"

        # LRU: Entferne älteste Einträge wenn Cache voll
        if len(self._cache) >= self._max_entries:
            # Entferne ersten (ältesten) Eintrag
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            print(f"[SimpleCacheRepository] LRU: Entfernt {oldest_key}")

        self._cache[cache_key] = candles
        print(f"[SimpleCacheRepository] Cached {len(candles)} candles für {cache_key}")

    def invalidate(self, timeframe: Optional[str] = None):
        """Invalidiert Cache"""
        if timeframe is None:
            self._cache.clear()
            print("[SimpleCacheRepository] Cache komplett invalidiert")
        else:
            # Entferne alle Einträge für Timeframe
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{timeframe}_")]
            for key in keys_to_remove:
                del self._cache[key]
            print(f"[SimpleCacheRepository] Cache für {timeframe} invalidiert ({len(keys_to_remove)} entries)")

    def is_initialized(self) -> bool:
        """Simple Cache ist immer initialisiert"""
        return True

    def get_performance_stats(self) -> Dict[str, Any]:
        """Performance Stats für Simple Cache"""
        return {
            'initialized': True,
            'cache_type': 'simple',
            'cached_entries': len(self._cache),
            'max_entries': self._max_entries
        }
