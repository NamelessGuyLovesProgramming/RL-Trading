"""
Batch CSV-Generierung für alle wichtigen Timeframes
Arbeitet mit begrenzten Datenmengen für bessere Performance
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
    print("Batch CSV-Generierung für alle Timeframes...")

    # Initialisierung
    nq_loader = NQDataLoader()
    aggregator = PerformanceAggregator()

    # Alle 1m Daten laden
    print("Lade komplette 1m Daten...")
    data_1m = nq_loader.load_year(2024)
    if data_1m is None or data_1m.empty:
        print("FEHLER: Keine 1m Daten!")
        return

    print(f"Geladen: {len(data_1m)} 1m Kerzen")

    # Alle wichtigen Timeframes
    timeframes = ['5m', '15m', '1h', '4h']

    for tf in timeframes:
        print(f"\n=== Generiere {tf} ===")

        # Ordner erstellen
        folder_path = Path(f"src/data/aggregated/{tf}")
        folder_path.mkdir(parents=True, exist_ok=True)

        try:
            # Verwende die bestehende get_aggregated_data_performance Methode
            # die bereits optimiert ist
            print(f"Aggregiere {tf} Daten...")

            # Direkte Nutzung der optimierten Methode
            aggregated_data = aggregator.get_aggregated_data_performance(data_1m, tf)

            if aggregated_data and len(aggregated_data) > 0:
                # In DataFrame konvertieren
                aggregated_df = pd.DataFrame(aggregated_data)

                # CSV speichern
                csv_path = folder_path / "nq-2024.csv"
                aggregated_df.to_csv(csv_path, index=False)

                print(f"ERFOLG: {len(aggregated_df)} {tf} Kerzen -> {csv_path}")

                # Größe und Zeitraum
                size_mb = csv_path.stat().st_size / (1024 * 1024)
                print(f"Größe: {size_mb:.2f} MB")

                if len(aggregated_df) > 0:
                    first_time = pd.to_datetime(aggregated_df.iloc[0]['timestamp'])
                    last_time = pd.to_datetime(aggregated_df.iloc[-1]['timestamp'])
                    print(f"Zeitraum: {first_time} bis {last_time}")
            else:
                print(f"WARNUNG: Keine aggregierten Daten für {tf}")

        except Exception as e:
            print(f"FEHLER bei {tf}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n=== CSV-Generierung abgeschlossen ===")

    # Übersicht
    print("\nGenerierte Dateien:")
    base_path = Path("src/data/aggregated")
    for tf in timeframes:
        csv_path = base_path / tf / "nq-2024.csv"
        if csv_path.exists():
            size_mb = csv_path.stat().st_size / (1024 * 1024)
            print(f"  {csv_path}: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()