"""
Test direkte CSV-Performance ohne PerformanceAggregator
"""
import pandas as pd
import time
from pathlib import Path

def test_direct_csv_loading():
    print("=== Direkte CSV Performance ===")

    timeframes = ['5m', '15m', '1h', '4h']
    visible_candles_tests = [50, 100, 200, 500]

    for tf in timeframes:
        print(f"\n--- {tf} Timeframe ---")

        csv_path = Path(f"src/data/aggregated/{tf}/nq-2024.csv")

        if not csv_path.exists():
            print(f"  FEHLER: {csv_path} existiert nicht!")
            continue

        for visible_candles in visible_candles_tests:
            start_time = time.time()

            try:
                # CSV laden
                df = pd.read_csv(csv_path)

                # Neueste N Kerzen nehmen (wie tail)
                if len(df) > visible_candles:
                    result_df = df.tail(visible_candles)
                else:
                    result_df = df

                # In Dictionary-Liste konvertieren (wie API erwartet)
                result_list = result_df.to_dict('records')

                end_time = time.time()
                duration = (end_time - start_time) * 1000  # in ms

                print(f"  {visible_candles:3d} candles: {len(result_list):4d} results in {duration:6.1f}ms")

                # Zeige erste und letzte Timestamps
                if len(result_list) > 0:
                    first_time = pd.to_datetime(result_list[0]['time'], unit='s')
                    last_time = pd.to_datetime(result_list[-1]['time'], unit='s')
                    print(f"       Zeitraum: {first_time} bis {last_time}")

            except Exception as e:
                end_time = time.time()
                duration = (end_time - start_time) * 1000
                print(f"  {visible_candles:3d} candles: FEHLER ({duration:6.1f}ms) - {e}")

if __name__ == "__main__":
    test_direct_csv_loading()