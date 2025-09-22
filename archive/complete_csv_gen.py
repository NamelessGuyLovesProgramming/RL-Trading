"""
Komplette CSV-Generierung für ALLE Timeframes
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
    print("=== Komplette CSV-Generierung für ALLE Timeframes ===")

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

    # Alle Timeframes (fehlende hinzufügen)
    timeframes = ['2m', '3m', '30m']  # Nur die fehlenden

    for tf in timeframes:
        print(f"\n=== Generiere {tf} ===")

        # Ordner erstellen
        folder_path = Path(f"src/data/aggregated/{tf}")
        folder_path.mkdir(parents=True, exist_ok=True)

        try:
            # Verwende get_aggregated_data_performance Methode
            aggregated_data = aggregator.get_aggregated_data_performance(data_1m, tf)

            if aggregated_data and len(aggregated_data) > 0:
                # In DataFrame konvertieren
                aggregated_df = pd.DataFrame(aggregated_data)

                # CSV speichern
                csv_path = folder_path / "nq-2024.csv"
                aggregated_df.to_csv(csv_path, index=False)

                print(f"ERFOLG: {len(aggregated_df)} {tf} Kerzen -> {csv_path}")

                # Größe
                size_mb = csv_path.stat().st_size / (1024 * 1024)
                print(f"Größe: {size_mb:.2f} MB")
            else:
                print(f"WARNUNG: Keine aggregierten Daten für {tf}")

        except Exception as e:
            print(f"FEHLER bei {tf}: {e}")
            import traceback
            traceback.print_exc()

    # Für 1m: Direkt die 1m Daten als CSV speichern
    print(f"\n=== Generiere 1m (direkt) ===")
    folder_path = Path("src/data/aggregated/1m")
    folder_path.mkdir(parents=True, exist_ok=True)

    try:
        # 1m Daten in API-Format konvertieren
        aggregated_data = []
        # Nur letzten 1000 Zeilen für bessere Performance
        data_1m_limited = data_1m.tail(1000)

        for timestamp, row in data_1m_limited.iterrows():
            aggregated_data.append({
                'time': int(timestamp.timestamp()),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        # In DataFrame konvertieren und speichern
        aggregated_df = pd.DataFrame(aggregated_data)
        csv_path = folder_path / "nq-2024.csv"
        aggregated_df.to_csv(csv_path, index=False)

        print(f"ERFOLG: {len(aggregated_df)} 1m Kerzen -> {csv_path}")
        size_mb = csv_path.stat().st_size / (1024 * 1024)
        print(f"Größe: {size_mb:.2f} MB")

    except Exception as e:
        print(f"FEHLER bei 1m: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n=== Generierung abgeschlossen ===")

if __name__ == "__main__":
    main()