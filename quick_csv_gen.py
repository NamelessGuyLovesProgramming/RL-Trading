"""
Schnelle CSV-Generierung für wichtigste Timeframes
"""
import os
import sys
import pandas as pd
from pathlib import Path

# Pfad für Imports hinzufügen
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data.nq_data_loader import NQDataLoader
from data.performance_aggregator import PerformanceAggregator

def main():
    print("Schnelle CSV-Generierung für 5m und 1h...")

    # Initialisierung
    nq_loader = NQDataLoader()
    aggregator = PerformanceAggregator()

    # 1m Daten laden
    print("Lade 1m Daten...")
    data_1m = nq_loader.load_year(2024)
    if data_1m is None or data_1m.empty:
        print("FEHLER: Keine 1m Daten!")
        return

    print(f"Geladen: {len(data_1m)} 1m Kerzen")

    # Nur wichtigste Timeframes
    timeframes = ['5m', '1h']

    for tf in timeframes:
        print(f"\nGeneriere {tf}...")

        # Ordner erstellen
        folder_path = Path(f"src/data/aggregated/{tf}")
        folder_path.mkdir(parents=True, exist_ok=True)

        # Aggregieren
        aggregated_df = aggregator.create_aggregated_dataframe(data_1m, tf)

        if aggregated_df is not None and not aggregated_df.empty:
            # Speichern
            csv_path = folder_path / "nq-2024.csv"
            aggregated_df.to_csv(csv_path, index=False)

            print(f"ERFOLG: {len(aggregated_df)} {tf} Kerzen -> {csv_path}")

            # Größe prüfen
            size_mb = csv_path.stat().st_size / (1024 * 1024)
            print(f"Größe: {size_mb:.2f} MB")
        else:
            print(f"FEHLER: Keine Daten für {tf}")

if __name__ == "__main__":
    main()