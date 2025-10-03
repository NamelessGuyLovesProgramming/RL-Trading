"""
Unified Price Repository
Single Source of Truth für konsistente Endkurse
Löst Endkurs-Inkonsistenz zwischen Timeframes
"""

from typing import List, Dict, Any, Optional
from datetime import datetime


class UnifiedPriceRepository:
    """Zentrale Price-Synchronisation für alle Timeframes - löst Endkurs-Inkonsistenz"""

    def __init__(self):
        self.master_price_timeline: Dict[int, Dict[str, Any]] = {}  # {timestamp: unified_price}
        self.timeframe_positions: Dict[str, int] = {}    # {timeframe: current_timestamp}
        self.base_candles_1m: List[Dict[str, Any]] = []  # 1-minute base data als Single Source of Truth
        self.initialized: bool = False
        self.price_sync_stats: Dict[str, int] = {'syncs': 0, 'corrections': 0}

    def initialize_with_1m_data(self, csv_1m_data: List[Dict[str, Any]]) -> None:
        """Initialize master price timeline with 1-minute CSV data"""
        if self.initialized:
            return

        print(f"[PRICE-REPO] Initializing master price timeline with {len(csv_1m_data)} 1m candles")

        for candle in csv_1m_data:
            timestamp = candle['time'] if isinstance(candle['time'], int) else int(candle['time'])
            self.master_price_timeline[timestamp] = {
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),  # Master close price
                'volume': int(candle.get('volume', 0))
            }

        self.base_candles_1m = csv_1m_data.copy()
        self.initialized = True
        print(f"[PRICE-REPO] Master timeline initialized: {len(self.master_price_timeline)} price points")

    def get_synchronized_price_at_time(self, target_timestamp: int, timeframe: str) -> float:
        """
        Gets synchronized price at specific timestamp for any timeframe

        Returns:
            float: Master-synchronisierter Endkurs (fallback 20000.0 wenn nicht initialisiert)
        """
        if not self.initialized:
            print(f"[PRICE-REPO] WARNING: Not initialized, returning fallback price")
            return 20000.0  # Fallback

        # Find closest timestamp in master timeline
        closest_timestamp = min(self.master_price_timeline.keys(),
                               key=lambda x: abs(x - target_timestamp))

        master_price = self.master_price_timeline[closest_timestamp]
        self.price_sync_stats['syncs'] += 1

        print(f"[PRICE-REPO] {timeframe} @ {target_timestamp} -> Master price: {master_price['close']:.2f}")
        return master_price['close']

    def synchronize_skip_event_prices(self, skip_time: datetime,
                                      generated_candles_by_timeframe: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Synchronizes all timeframe candles to same price at skip time"""
        if not self.initialized:
            print(f"[PRICE-REPO] Cannot sync - not initialized")
            return generated_candles_by_timeframe

        target_timestamp = int(skip_time.timestamp())
        master_price = self.get_synchronized_price_at_time(target_timestamp, "master")

        synchronized_candles: Dict[str, List[Dict[str, Any]]] = {}
        for timeframe, candles in generated_candles_by_timeframe.items():
            if not candles:
                synchronized_candles[timeframe] = []
                continue

            sync_candles: List[Dict[str, Any]] = []
            for candle in candles:
                sync_candle = candle.copy()

                # CRITICAL: Synchronize close price to master price
                old_close = sync_candle['close']
                sync_candle['close'] = master_price

                # Adjust OHLC to maintain realistic relationships
                if sync_candle['open'] > master_price:
                    sync_candle['open'] = master_price
                if sync_candle['high'] < master_price:
                    sync_candle['high'] = master_price + 0.25  # Small buffer
                if sync_candle['low'] > master_price:
                    sync_candle['low'] = master_price - 0.25   # Small buffer

                sync_candles.append(sync_candle)

                if old_close != master_price:
                    self.price_sync_stats['corrections'] += 1
                    print(f"[PRICE-REPO] {timeframe} price corrected: {old_close:.2f} -> {master_price:.2f}")

            synchronized_candles[timeframe] = sync_candles

        print(f"[PRICE-REPO] Skip event synchronized: {len(synchronized_candles)} timeframes")
        return synchronized_candles

    def update_timeframe_position(self, timeframe: str, timestamp: int) -> None:
        """Updates current position for timeframe"""
        self.timeframe_positions[timeframe] = timestamp

    def get_price_sync_stats(self) -> Dict[str, int]:
        """Returns synchronization statistics"""
        return self.price_sync_stats.copy()

    def reset_stats(self) -> None:
        """Reset synchronization statistics"""
        self.price_sync_stats = {'syncs': 0, 'corrections': 0}
