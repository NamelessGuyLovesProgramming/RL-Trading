"""
Einmaliges Pre-Aggregation Script fuer alle Timeframes
Generiert CSV-Dateien in Option 2 Ordnerstruktur: src/data/aggregated/{timeframe}/
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Pfad fuer Imports hinzufuegen
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data.performance_aggregator import PerformanceAggregator
from data.nq_data_loader import NQDataLoader

def create_aggregated_folders():
    """Erstellt die Ordnerstruktur fuer aggregierte Daten"""
    base_path = Path("src/data/aggregated")
    timeframes = ['2m', '3m', '5m', '15m', '30m', '1h', '4h']

    for tf in timeframes:
        folder_path = base_path / tf
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"+ Ordner erstellt: {folder_path}")

def generate_aggregated_csvs():
    """Generiert alle aggregierten CSV-Dateien fuer NQ Asset"""
    print("Starte einmalige Pre-Aggregation fuer NQ...")

    # Ordnerstruktur erstellen
    create_aggregated_folders()

    # NQ Data Loader und PerformanceAggregator initialisieren
    nq_loader = NQDataLoader()
    aggregator = PerformanceAggregator()

    # 1m Daten laden (wie im chart_server)
    print("Lade 1m Basisdaten...")
    data_1m = nq_loader.load_year(2024)
    if data_1m is None or data_1m.empty:
        print("FEHLER: Keine 1m Daten gefunden!")
        return

    print(f"+ 1m Daten geladen: {len(data_1m)} Kerzen")

    # Alle Timeframes aggregieren und speichern
    timeframes = ['2m', '3m', '5m', '15m', '30m', '1h', '4h']

    for tf in timeframes:
        print(f"\nAggregiere {tf}...")

        try:
            # Aggregierte Daten erstellen
            aggregated_df = aggregator.create_aggregated_dataframe(data_1m, tf)

            if aggregated_df is None or aggregated_df.empty:
                print(f"FEHLER: Keine aggregierten Daten fuer {tf}")
                continue

            # CSV-Pfad definieren
            csv_path = Path(f"src/data/aggregated/{tf}/nq-2024.csv")

            # CSV speichern
            aggregated_df.to_csv(csv_path, index=False)

            print(f"ERFOLG {tf}: {len(aggregated_df)} Kerzen -> {csv_path}")

            # Erste und letzte Kerze anzeigen
            if len(aggregated_df) > 0:
                first_time = pd.to_datetime(aggregated_df.iloc[0]['timestamp'])
                last_time = pd.to_datetime(aggregated_df.iloc[-1]['timestamp'])
                print(f"   Zeitraum: {first_time} bis {last_time}")

        except Exception as e:
            print(f"FEHLER bei {tf}: {e}")

    print("\nPre-Aggregation abgeschlossen!")
    print("\nUebersicht generierte Dateien:")

    # Uebersicht der generierten Dateien
    base_path = Path("src/data/aggregated")
    for tf in timeframes:
        csv_path = base_path / tf / "nq-2024.csv"
        if csv_path.exists():
            size_mb = csv_path.stat().st_size / (1024 * 1024)
            print(f"   {csv_path}: {size_mb:.2f} MB")

if __name__ == "__main__":
    print("=" * 60)
    print("EINMALIGE PRE-AGGREGATION FUER NQ ASSET")
    print("=" * 60)

    generate_aggregated_csvs()

    print("\n" + "=" * 60)
    print("Fertig! CSV-Dateien sind bereit fuer schnelles Laden.")
    print("=" * 60)