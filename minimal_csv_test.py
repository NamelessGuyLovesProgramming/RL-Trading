"""
Minimaler Test für CSV-Generierung
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
    print("Minimaler CSV-Test...")

    # Initialisierung
    nq_loader = NQDataLoader()
    aggregator = PerformanceAggregator()

    # Nur kleine Menge 1m Daten laden (letzten 1000 Zeilen)
    print("Lade begrenzte 1m Daten...")
    data_1m = nq_loader.load_year(2024)
    if data_1m is None or data_1m.empty:
        print("FEHLER: Keine 1m Daten!")
        return

    # Nur letzten 1000 Zeilen für Test
    data_1m_small = data_1m.tail(1000)
    print(f"Test mit {len(data_1m_small)} 1m Kerzen")

    # Test mit 5m
    print("Teste 5m Aggregation...")

    # Ordner erstellen
    folder_path = Path("src/data/aggregated/5m")
    folder_path.mkdir(parents=True, exist_ok=True)

    try:
        # Aggregieren
        aggregated_df = aggregator.create_aggregated_dataframe(data_1m_small, '5m')

        if aggregated_df is not None and not aggregated_df.empty:
            # Speichern
            csv_path = folder_path / "nq-2024.csv"
            aggregated_df.to_csv(csv_path, index=False)

            print(f"ERFOLG: {len(aggregated_df)} 5m Kerzen erstellt")
            print(f"Datei: {csv_path}")

            # Erste paar Zeilen anzeigen
            print("Erste 3 Zeilen:")
            print(aggregated_df.head(3))
        else:
            print("FEHLER: Aggregation fehlgeschlagen")
    except Exception as e:
        print(f"FEHLER: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()