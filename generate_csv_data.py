"""
CSV-Daten Generierung für alle Timeframes
Erstellt pre-aggregierte CSV-Dateien für NQ in src/data/aggregated/
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Pfad für Imports hinzufügen
sys.path.append('src')

from data.performance_aggregator import PerformanceAggregator
from data.nq_data_loader import NQDataLoader

def main():
    print("Starte CSV-Generierung für alle Timeframes...")
    print("=" * 50)

    # Aggregated Directory erstellen
    aggregated_dir = "src/data/aggregated"
    os.makedirs(aggregated_dir, exist_ok=True)
    print(f"Aggregated Directory: {aggregated_dir}")

    # NQ Data Loader initialisieren
    print("Lade NQ 1m Daten...")
    loader = NQDataLoader()

    # 2024 Daten laden
    raw_1m_data = loader.load_year(2024)
    print(f"Geladen: {len(raw_1m_data)} 1m Kerzen für 2024")
    print(f"Zeitraum: {raw_1m_data.index.min()} bis {raw_1m_data.index.max()}")

    # Performance Aggregator initialisieren
    aggregator = PerformanceAggregator()

    # Alle Timeframes generieren
    timeframes = ['2m', '3m', '5m', '15m', '30m', '1h', '4h']

    for timeframe in timeframes:
        print(f"\nGeneriere {timeframe} CSV...")

        try:
            # CSV-Datei Pfad
            csv_file = os.path.join(aggregated_dir, f"nq-{timeframe}-2024.csv")

            # Prüfe ob bereits existiert
            if os.path.exists(csv_file):
                print(f"  {timeframe}: Bereits vorhanden - {csv_file}")
                # Lade und prüfe Daten
                df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
                print(f"  {timeframe}: {len(df)} Kerzen in CSV")
                continue

            # Aggregiere Daten
            aggregated_data = aggregator.aggregate_timeframe(raw_1m_data, timeframe)

            # Als CSV speichern
            aggregated_data.to_csv(csv_file)
            print(f"  {timeframe}: {len(aggregated_data)} Kerzen -> {csv_file}")

            # Kurze Validierung
            if len(aggregated_data) > 0:
                first_candle = aggregated_data.iloc[0]
                last_candle = aggregated_data.iloc[-1]
                print(f"  {timeframe}: {first_candle.name} bis {last_candle.name}")

        except Exception as e:
            print(f"  FEHLER bei {timeframe}: {e}")

    print("\nCSV-Generierung abgeschlossen!")

    # Test laden der CSV-Dateien
    print("\nTeste CSV-Laden...")
    for timeframe in timeframes:
        csv_file = os.path.join(aggregated_dir, f"nq-{timeframe}-2024.csv")
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
                print(f"  {timeframe}: {len(df)} Kerzen erfolgreich geladen")
            except Exception as e:
                print(f"  FEHLER beim Laden {timeframe}: {e}")
        else:
            print(f"  {timeframe}: CSV nicht gefunden")

if __name__ == "__main__":
    main()