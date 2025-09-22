"""
Test CSV-Dateien laden
"""
import pandas as pd
from pathlib import Path

def test_csv_files():
    print("=== CSV-Dateien Test ===")

    timeframes = ['5m', '15m', '1h', '4h']

    for tf in timeframes:
        csv_path = Path(f"src/data/aggregated/{tf}/nq-2024.csv")

        if csv_path.exists():
            # CSV laden
            df = pd.read_csv(csv_path)

            print(f"\n{tf} CSV:")
            print(f"  Datei: {csv_path}")
            print(f"  Zeilen: {len(df)}")
            print(f"  Spalten: {list(df.columns)}")
            print(f"  Erste Zeile: {df.iloc[0].to_dict()}")
            print(f"  Letzte Zeile: {df.iloc[-1].to_dict()}")

        else:
            print(f"\nFEHLER: {csv_path} existiert nicht!")

if __name__ == "__main__":
    test_csv_files()