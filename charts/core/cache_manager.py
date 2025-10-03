"""
Cache Manager für Chart-Daten
Enthält ChartDataCache für ultra-schnelles Memory-basiertes Caching
"""

import pandas as pd
from pathlib import Path


class ChartDataCache:
    """
    Ultra-schneller Memory-basierter Data Cache für alle Timeframes
    Lädt alle CSV-Dateien einmalig beim Start -> Sub-Millisekunden Navigation
    """

    def __init__(self):
        """Initialisiert leeren Cache"""
        self.timeframe_data = {}  # {timeframe: pandas.DataFrame}
        self.loaded_timeframes = set()
        self.available_timeframes = ["1m", "2m", "3m", "5m", "15m", "30m", "1h", "4h"]  # CORRECTED: Alle Timeframe-Ordner verfügbar
        print("[CACHE] ChartDataCache initialisiert")

    def load_all_timeframes(self):
        """Lädt alle verfügbaren Timeframes in Memory - einmalig beim Server-Start"""
        print("[CACHE] Starte Memory-Loading aller Timeframes...")

        for timeframe in self.available_timeframes:
            csv_path = Path(f"src/data/aggregated/{timeframe}/nq-2024.csv")

            if csv_path.exists():
                try:
                    # CSV mit neuer Struktur laden (Date, Time, OHLCV)
                    df = pd.read_csv(csv_path)

                    # DateTime kombinieren und als zusätzliche Spalte hinzufügen
                    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
                    df['time'] = df['datetime'].astype(int) // 10**9  # Unix timestamp für TradingView

                    # Sortierung nach Datum sicherstellen
                    df = df.sort_values('datetime')

                    self.timeframe_data[timeframe] = df
                    self.loaded_timeframes.add(timeframe)

                    # Debug Info
                    start_time = df['datetime'].iloc[0]
                    end_time = df['datetime'].iloc[-1]

                    print(f"[CACHE] SUCCESS {timeframe} loaded: {len(df)} candles ({start_time} bis {end_time})")

                except Exception as e:
                    print(f"[CACHE] ERROR beim Laden {timeframe}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[CACHE] WARNING CSV nicht gefunden: {csv_path}")

        print(f"[CACHE] Memory-Loading abgeschlossen: {len(self.loaded_timeframes)} Timeframes geladen")
        return len(self.loaded_timeframes) > 0

    def load_priority_timeframes(self, priority_list):
        """Lädt nur prioritäre Timeframes für schnellen Server-Start"""
        print(f"[CACHE] Lade Priority Timeframes: {priority_list}")

        for timeframe in priority_list:
            if timeframe not in self.available_timeframes:
                continue

            csv_path = Path(f"src/data/aggregated/{timeframe}/nq-2024.csv")

            if csv_path.exists():
                try:
                    # CSV mit neuer Struktur laden (Date, Time, OHLCV)
                    df = pd.read_csv(csv_path)

                    # DateTime kombinieren und als zusätzliche Spalte hinzufügen
                    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
                    df['time'] = df['datetime'].astype(int) // 10**9  # Unix timestamp für TradingView

                    # Sortierung nach Datum sicherstellen
                    df = df.sort_values('datetime')

                    self.timeframe_data[timeframe] = df
                    self.loaded_timeframes.add(timeframe)

                    # Debug Info
                    start_time = df['datetime'].iloc[0]
                    end_time = df['datetime'].iloc[-1]

                    print(f"[CACHE] SUCCESS {timeframe} loaded: {len(df)} candles ({start_time.strftime('%Y-%m-%d')} bis {end_time.strftime('%Y-%m-%d')})")

                except Exception as e:
                    print(f"[CACHE] ERROR beim Laden {timeframe}: {e}")
            else:
                print(f"[CACHE] WARNING CSV nicht gefunden: {csv_path}")

        print(f"[CACHE] Priority Loading abgeschlossen: {len(self.loaded_timeframes)} von {len(priority_list)} geladen")
        return len(self.loaded_timeframes) > 0

    def find_best_date_index(self, target_date, timeframe):
        """
        Findet den besten Index für ein Zieldatum mit intelligenten Fallback-Strategien

        Args:
            target_date: datetime object
            timeframe: string (z.B. '5m')

        Returns:
            int: Index im DataFrame der am besten zum Zieldatum passt
        """
        if timeframe not in self.timeframe_data:
            raise ValueError(f"Timeframe {timeframe} nicht geladen!")

        df = self.timeframe_data[timeframe]
        target_timestamp = int(target_date.timestamp())

        # Check if target is before CSV data range
        if target_timestamp < df['time'].iloc[0]:
            print(f"[CACHE] Datum {target_date} vor CSV-Bereich - verwende ersten verfügbaren Index (0)")
            return 0  # FIXED: Verwende ersten verfügbaren Datenpunkt statt willkürlichen Index 199

        # Check if target is after CSV data range
        elif target_timestamp > df['time'].iloc[-1]:
            print(f"[CACHE] Datum {target_date} nach CSV-Bereich - verwende letzten Index")
            return len(df) - 1

        # Find nearest timestamp match
        else:
            time_diffs = (df['time'] - target_timestamp).abs()
            best_index = time_diffs.idxmin()

            matched_time = pd.to_datetime(df.iloc[best_index]['time'], unit='s')
            print(f"[CACHE] Exakte Übereinstimmung: Index {best_index} -> {matched_time}")

            return best_index

    def get_candles_range(self, timeframe, center_index, total_candles=10, visible_candles=5):
        """
        Holt einen Bereich von Kerzen rund um center_index

        Args:
            timeframe: string
            center_index: int - Zentrum des Bereichs
            total_candles: int - Gesamt zu ladende Kerzen (200)
            visible_candles: int - Sichtbare Kerzen im Chart (5)

        Returns:
            dict: {
                'data': list - Chart-formatierte Daten (5 Kerzen),
                'visible_start': int - Index der ersten sichtbaren Kerze,
                'visible_end': int - Index der letzten sichtbaren Kerze,
                'center_index': int - Ursprungsindex,
                'total_count': int
            }
        """
        if timeframe not in self.timeframe_data:
            raise ValueError(f"Timeframe {timeframe} nicht geladen!")

        df = self.timeframe_data[timeframe]
        df_length = len(df)

        # Berechne Start/End Index für total_candles (200) Kerzen VOR center_index
        start_idx = max(0, center_index - total_candles + 1)  # 199 Kerzen davor + 1 center = 200
        end_idx = center_index + 1  # Bis einschließlich center_index

        # Falls nicht genug Daten vor center_index, fülle nach vorne auf
        if end_idx - start_idx < total_candles:
            needed = total_candles - (end_idx - start_idx)
            end_idx = min(df_length, end_idx + needed)

        # Extrahiere DataFrame-Bereich
        result_df = df.iloc[start_idx:end_idx]

        # Konvertiere zu Chart-Format
        chart_data = []
        for _, row in result_df.iterrows():
            chart_data.append({
                'time': int(row['time']),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })

        # Berechne sichtbaren Bereich (letzten visible_candles von total_candles)
        data_count = len(chart_data)
        visible_start = max(0, data_count - visible_candles)
        visible_end = data_count - 1

        print(f"[CACHE] Kerzen-Bereich: {data_count} total, sichtbar {visible_start}-{visible_end} (CSV Index {start_idx}-{end_idx-1})")

        return {
            'data': chart_data,
            'visible_start': visible_start,
            'visible_end': visible_end,
            'center_index': center_index,
            'total_count': data_count,
            'csv_range': (start_idx, end_idx - 1)
        }

    def get_next_candle(self, timeframe, current_index):
        """
        Holt die nächste Kerze für Skip-Operation

        Args:
            timeframe: string
            current_index: int - Aktueller Index im DataFrame

        Returns:
            dict: {'candle': {chart_data}, 'new_index': int} oder None wenn Ende erreicht
        """
        if timeframe not in self.timeframe_data:
            raise ValueError(f"Timeframe {timeframe} nicht geladen!")

        df = self.timeframe_data[timeframe]
        next_index = current_index + 1

        if next_index >= len(df):
            print(f"[CACHE] Ende der {timeframe} Daten erreicht (Index {current_index})")
            return None

        # Nächste Kerze extrahieren
        next_row = df.iloc[next_index]
        next_candle = {
            'time': int(next_row['time']),
            'open': float(next_row['Open']),
            'high': float(next_row['High']),
            'low': float(next_row['Low']),
            'close': float(next_row['Close']),
            'volume': int(next_row['Volume'])
        }

        next_time = pd.to_datetime(next_row['time'], unit='s')
        print(f"[CACHE] Skip: Index {current_index} -> {next_index} ({next_time})")

        return {
            'candle': next_candle,
            'new_index': next_index
        }

    def get_timeframe_info(self, timeframe):
        """Gibt Info über einen geladenen Timeframe zurück"""
        if timeframe not in self.timeframe_data:
            return None

        df = self.timeframe_data[timeframe]
        start_time = pd.to_datetime(df['time'].iloc[0], unit='s')
        end_time = pd.to_datetime(df['time'].iloc[-1], unit='s')

        return {
            'timeframe': timeframe,
            'total_candles': len(df),
            'start_time': start_time,
            'end_time': end_time,
            'loaded': True
        }
