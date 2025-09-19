"""
NQ Data Loader
Lädt und verarbeitet NQ-1M CSV Dateien von 2020-2025
"""

import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import glob

class NQDataLoader:
    def __init__(self, data_path: str = "src/data/nq-1m/nq-1m"):
        self.data_path = data_path
        self.available_files = self._scan_files()

    def _scan_files(self) -> Dict[int, str]:
        """Scannt verfügbare NQ CSV Dateien"""
        files = {}
        pattern = os.path.join(self.data_path, "nq-1m*.csv")

        for file_path in glob.glob(pattern):
            filename = os.path.basename(file_path)
            # Extrahiere Jahr aus Dateiname (z.B. nq-1m2024.csv -> 2024)
            if "nq-1m" in filename and ".csv" in filename:
                year_str = filename.replace("nq-1m", "").replace(".csv", "")
                try:
                    year = int(year_str)
                    files[year] = file_path
                except ValueError:
                    continue

        return files

    def load_year(self, year: int) -> Optional[pd.DataFrame]:
        """Lädt Daten für ein spezifisches Jahr"""
        if year not in self.available_files:
            print(f"Jahr {year} nicht verfügbar. Verfügbar: {list(self.available_files.keys())}")
            return None

        file_path = self.available_files[year]
        print(f"Lade NQ-1M Daten für {year} aus {file_path}")

        try:
            df = pd.read_csv(file_path)

            # Kombiniere Date und Time zu Datetime - verwende mixed format für Kompatibilität
            df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed')

            # Entferne ursprüngliche Date/Time Spalten
            df = df.drop(['Date', 'Time'], axis=1)

            # Setze DateTime als Index
            df = df.set_index('DateTime')

            # Sortiere nach Zeit
            df = df.sort_index()

            print(f"{len(df)} Kerzen geladen für {year}")
            print(f"Zeitraum: {df.index[0]} bis {df.index[-1]}")

            return df

        except Exception as e:
            print(f"Fehler beim Laden von {file_path}: {e}")
            return None

    def load_date_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Lädt Daten für einen bestimmten Datumsbereich

        Args:
            start_date: Start-Datum im Format 'YYYY-MM-DD'
            end_date: End-Datum im Format 'YYYY-MM-DD'
        """
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        start_year = start_dt.year
        end_year = end_dt.year

        # Lade alle benötigten Jahre
        all_data = []
        for year in range(start_year, end_year + 1):
            year_data = self.load_year(year)
            if year_data is not None:
                all_data.append(year_data)

        if not all_data:
            print(f"Keine Daten für Zeitraum {start_date} bis {end_date} gefunden")
            return pd.DataFrame()

        # Kombiniere alle Jahre
        combined_df = pd.concat(all_data)
        combined_df = combined_df.sort_index()

        # Filtere auf gewünschten Datumsbereich
        mask = (combined_df.index >= start_dt) & (combined_df.index <= end_dt)
        filtered_df = combined_df[mask]

        print(f"{len(filtered_df)} Kerzen für Zeitraum {start_date} bis {end_date}")

        return filtered_df

    def load_latest_days(self, days: int = 30) -> pd.DataFrame:
        """Lädt die letzten N Tage an Daten"""
        # Finde das neueste verfügbare Jahr
        latest_year = max(self.available_files.keys())
        latest_data = self.load_year(latest_year)

        if latest_data is None or len(latest_data) == 0:
            return pd.DataFrame()

        # Berechne Start-Datum (N Tage vor dem letzten verfügbaren Datum)
        end_date = latest_data.index[-1]
        start_date = end_date - timedelta(days=days)

        # Filtere Daten
        mask = latest_data.index >= start_date
        recent_data = latest_data[mask]

        print(f"{len(recent_data)} Kerzen für die letzten {days} Tage")
        print(f"Zeitraum: {recent_data.index[0]} bis {recent_data.index[-1]}")

        return recent_data

    def convert_to_chart_format(self, df: pd.DataFrame) -> List[Dict]:
        """Konvertiert DataFrame zu LightweightCharts Format mit Unix-Timestamps"""
        if df.empty:
            return []

        chart_data = []
        for timestamp, row in df.iterrows():
            # Konvertiere zu Unix-Timestamp (Sekunden seit 1970)
            unix_timestamp = int(timestamp.timestamp())

            chart_data.append({
                'time': unix_timestamp,  # Unix-Timestamp für LightweightCharts
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume']) if 'Volume' in row else 0
            })

        return chart_data

    def get_info(self) -> Dict:
        """Gibt Informationen über verfügbare Daten zurück"""
        info = {
            'available_years': list(self.available_files.keys()),
            'total_files': len(self.available_files),
            'data_path': self.data_path
        }

        # Lade ein Jahr als Beispiel für mehr Details
        if self.available_files:
            sample_year = max(self.available_files.keys())
            sample_data = self.load_year(sample_year)
            if sample_data is not None:
                info['sample_year'] = sample_year
                info['sample_records'] = len(sample_data)
                info['sample_start'] = str(sample_data.index[0])
                info['sample_end'] = str(sample_data.index[-1])

        return info

def test_loader():
    """Test-Funktion für den Data Loader"""
    print("Teste NQ Data Loader...")

    loader = NQDataLoader()

    # Info anzeigen
    info = loader.get_info()
    print(f"Verfügbare Jahre: {info['available_years']}")

    # Lade 2024 Daten (letzte 7 Tage)
    data_2024 = loader.load_year(2024)
    if data_2024 is not None:
        recent_data = data_2024.tail(7 * 24 * 60)  # 7 Tage * 24 Stunden * 60 Minuten

    if not recent_data.empty:
        # Konvertiere zu Chart-Format
        chart_data = loader.convert_to_chart_format(recent_data)
        print(f"Chart-Format: {len(chart_data)} Kerzen")
        print(f"Erste Kerze: {chart_data[0] if chart_data else 'Keine'}")
        print(f"Letzte Kerze: {chart_data[-1] if chart_data else 'Keine'}")

    print("Test abgeschlossen")

if __name__ == "__main__":
    test_loader()