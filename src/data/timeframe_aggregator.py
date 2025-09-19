"""
Timeframe Aggregator
Aggregiert 1-Minuten-Daten zu höheren Timeframes mit intelligentem Caching
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import os

class TimeframeAggregator:
    def __init__(self, cache_dir: str = "src/data/cache"):
        self.cache_dir = cache_dir
        self.timeframe_minutes = {
            '1m': 1,
            '2m': 2,
            '3m': 3,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240
        }

        # Erstelle Cache-Verzeichnis falls nicht vorhanden
        os.makedirs(cache_dir, exist_ok=True)

        # In-Memory Cache für aggregierte Daten
        self.memory_cache = {}

        print(f"TimeframeAggregator initialisiert - Cache: {cache_dir}")

    def get_cache_key(self, timeframe: str, start_date: str, end_date: str) -> str:
        """Erstellt einen eindeutigen Cache-Key für die Daten"""
        return f"{timeframe}_{start_date}_{end_date}"

    def get_cache_filename(self, cache_key: str) -> str:
        """Gibt den Dateipfad für Cache-Daten zurück"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")

    def load_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Lädt aggregierte Daten aus dem Cache"""
        # Prüfe In-Memory Cache zuerst
        if cache_key in self.memory_cache:
            print(f"Memory Cache Hit für {cache_key}")
            return self.memory_cache[cache_key]

        # Prüfe File Cache
        cache_file = self.get_cache_filename(cache_key)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                # Lade in Memory Cache
                self.memory_cache[cache_key] = data
                print(f"File Cache Hit für {cache_key} - {len(data)} Kerzen")
                return data
            except Exception as e:
                print(f"Fehler beim Laden aus Cache {cache_file}: {e}")

        return None

    def save_to_cache(self, cache_key: str, data: List[Dict]):
        """Speichert aggregierte Daten im Cache"""
        # Speichere in Memory Cache
        self.memory_cache[cache_key] = data

        # Speichere in File Cache
        cache_file = self.get_cache_filename(cache_key)
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            print(f"Cache gespeichert: {cache_key} - {len(data)} Kerzen")
        except Exception as e:
            print(f"Fehler beim Speichern in Cache {cache_file}: {e}")

    def aggregate_timeframe(self, base_data: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """Aggregiert 1m-Daten zu einem höheren Timeframe"""
        if target_timeframe not in self.timeframe_minutes:
            raise ValueError(f"Unbekannter Timeframe: {target_timeframe}")

        if target_timeframe == '1m':
            return base_data

        minutes = self.timeframe_minutes[target_timeframe]
        print(f"Aggregiere zu {target_timeframe} ({minutes} Minuten)...")

        # Gruppiere nach Zeitintervallen
        base_data = base_data.sort_index()

        # Berechne Gruppierungsintervall
        # Für jede Kerze: Finde das Start-Intervall
        def get_interval_start(timestamp):
            # Runde auf das entsprechende Intervall ab
            minute = timestamp.minute
            rounded_minute = (minute // minutes) * minutes
            return timestamp.replace(minute=rounded_minute, second=0, microsecond=0)

        # Erstelle Gruppierungs-Key
        base_data['interval_start'] = base_data.index.map(get_interval_start)

        # Aggregiere nach Intervall
        aggregated = base_data.groupby('interval_start').agg({
            'Open': 'first',   # Erster Open-Wert
            'High': 'max',     # Höchster High-Wert
            'Low': 'min',      # Niedrigster Low-Wert
            'Close': 'last',   # Letzter Close-Wert
            'Volume': 'sum'    # Summe des Volumens
        })

        # Entferne die Hilfsspalte
        aggregated = aggregated.dropna()

        print(f"Aggregiert: {len(base_data)} -> {len(aggregated)} Kerzen ({target_timeframe})")
        return aggregated

    def get_aggregated_data(self, base_data: pd.DataFrame, timeframe: str) -> List[Dict]:
        """Holt aggregierte Daten mit intelligentem Caching"""
        if timeframe == '1m':
            # Keine Aggregation nötig - konvertiere direkt zu Chart-Format
            return self.convert_to_chart_format(base_data)

        # Erstelle Cache-Key basierend auf Datenbereich
        start_date = base_data.index[0].strftime('%Y-%m-%d')
        end_date = base_data.index[-1].strftime('%Y-%m-%d')
        cache_key = self.get_cache_key(timeframe, start_date, end_date)

        # Prüfe Cache
        cached_data = self.load_from_cache(cache_key)
        if cached_data is not None:
            return cached_data

        # Aggregiere Daten
        aggregated_df = self.aggregate_timeframe(base_data, timeframe)
        chart_data = self.convert_to_chart_format(aggregated_df)

        # Speichere im Cache
        self.save_to_cache(cache_key, chart_data)

        return chart_data

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

    def precompute_all_timeframes(self, base_data: pd.DataFrame):
        """Berechnet alle Timeframes vor und speichert sie im Cache"""
        print("Precomputing alle Timeframes...")

        start_date = base_data.index[0].strftime('%Y-%m-%d')
        end_date = base_data.index[-1].strftime('%Y-%m-%d')

        for timeframe in self.timeframe_minutes.keys():
            if timeframe == '1m':
                continue  # Skip 1m da es die Basis-Daten sind

            print(f"Precomputing {timeframe}...")
            self.get_aggregated_data(base_data, timeframe)

        print("Alle Timeframes precomputed")

    def clear_cache(self):
        """Löscht den gesamten Cache"""
        # Leere Memory Cache
        self.memory_cache.clear()

        # Lösche File Cache
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.cache_dir, filename)
                    try:
                        os.remove(file_path)
                        print(f"Cache-Datei geloescht: {filename}")
                    except Exception as e:
                        print(f"Fehler beim Loeschen von {filename}: {e}")

        print("Cache komplett geleert")

    def get_cache_info(self) -> Dict:
        """Gibt Informationen über den Cache zurück"""
        info = {
            'memory_cache_size': len(self.memory_cache),
            'file_cache_files': 0,
            'cache_dir': self.cache_dir,
            'supported_timeframes': list(self.timeframe_minutes.keys())
        }

        if os.path.exists(self.cache_dir):
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.json')]
            info['file_cache_files'] = len(cache_files)
            info['file_cache_list'] = cache_files

        return info

def test_aggregator():
    """Test-Funktion für den Timeframe Aggregator"""
    print("Teste Timeframe Aggregator...")

    # Erstelle Test-Daten (simuliert 1 Tag 1m-Daten)
    import numpy as np

    dates = pd.date_range(start='2024-01-01 09:30:00', periods=390, freq='1min')  # 6.5 Stunden Handelstag

    # Simuliere OHLCV-Daten
    base_price = 100.0
    test_data = []

    for i, timestamp in enumerate(dates):
        # Simuliere Preisbewegung
        price_change = np.random.normal(0, 0.1)
        current_price = base_price + price_change

        # OHLC um den aktuellen Preis
        high = current_price + abs(np.random.normal(0, 0.05))
        low = current_price - abs(np.random.normal(0, 0.05))
        open_price = base_price  # Vorheriger Close
        close_price = current_price
        volume = np.random.randint(1000, 5000)

        test_data.append({
            'Open': open_price,
            'High': high,
            'Low': low,
            'Close': close_price,
            'Volume': volume
        })

        base_price = current_price

    # Erstelle DataFrame
    df = pd.DataFrame(test_data, index=dates)

    # Teste Aggregator
    aggregator = TimeframeAggregator()

    # Teste verschiedene Timeframes
    for tf in ['2m', '5m', '15m', '30m', '1h']:
        print(f"\nTeste {tf}:")
        aggregated_data = aggregator.get_aggregated_data(df, tf)
        print(f"Ergebnis: {len(aggregated_data)} Kerzen")
        if aggregated_data:
            print(f"Erste Kerze: {aggregated_data[0]}")
            print(f"Letzte Kerze: {aggregated_data[-1]}")

    # Cache Info
    cache_info = aggregator.get_cache_info()
    print(f"\nCache Info: {cache_info}")

    print("Test abgeschlossen")

if __name__ == "__main__":
    test_aggregator()