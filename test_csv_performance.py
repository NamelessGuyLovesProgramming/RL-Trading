"""
Test CSV-Performance direkt
"""
import pandas as pd
import time
from pathlib import Path
import sys
import os

# Pfad für Imports hinzufügen
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data.performance_aggregator import PerformanceAggregator

def test_csv_performance():
    print("=== CSV Performance Test ===")

    aggregator = PerformanceAggregator()

    timeframes = ['5m', '15m', '1h', '4h']
    visible_candles_tests = [50, 100, 200, 500]

    for tf in timeframes:
        print(f"\n--- {tf} Timeframe ---")

        for visible_candles in visible_candles_tests:
            start_time = time.time()

            try:
                # Test der get_aggregated_data_from_csv Methode
                result = aggregator.get_aggregated_data_from_csv(
                    base_data=None,  # Wird nicht benötigt für CSV-Laden
                    timeframe=tf,
                    visible_candles=visible_candles
                )

                end_time = time.time()
                duration = (end_time - start_time) * 1000  # in ms

                if result:
                    print(f"  {visible_candles:3d} candles: {len(result):4d} results in {duration:6.1f}ms")
                else:
                    print(f"  {visible_candles:3d} candles: FEHLER - keine Daten")

            except Exception as e:
                end_time = time.time()
                duration = (end_time - start_time) * 1000
                print(f"  {visible_candles:3d} candles: FEHLER ({duration:6.1f}ms) - {e}")

if __name__ == "__main__":
    test_csv_performance()