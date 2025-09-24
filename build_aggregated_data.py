#!/usr/bin/env python3
"""
RL Trading - Data Aggregation Script
Verarbeitet src/data/nq-1m/nq-1m/nq-1m2024.csv und erstellt:
1. Monatliche Aufteilung (Januar bis Dezember)
2. Timeframe Aggregationen (1m -> 2m, 3m, 5m, 15m, 30m, 1h, 4h)
3. Korrekte Verzeichnisstruktur für Memory Cache System
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import os

def load_source_data():
    """Lädt die 1-Minuten Quelldaten"""
    source_file = Path("src/data/nq-1m/nq-1m/nq-1m2024.csv")

    if not source_file.exists():
        raise FileNotFoundError(f"Quelldatei nicht gefunden: {source_file}")

    print(f"Lade Quelldaten: {source_file} ({source_file.stat().st_size / 1024 / 1024:.1f} MB)")

    # CSV mit korrektem Format laden
    df = pd.read_csv(source_file)

    # DateTime kombinieren und als Index setzen (mit flexiblem Format)
    df['datetime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='mixed', dayfirst=True)
    df = df.set_index('datetime')

    # Nur OHLCV Spalten behalten
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

    # Nach Datum sortieren
    df = df.sort_index()

    print(f"Daten geladen: {len(df)} Kerzen von {df.index[0]} bis {df.index[-1]}")

    return df

def aggregate_timeframe(df, timeframe):
    """Aggregiert 1-Minuten Daten zu gewünschtem Timeframe"""

    # Timeframe mapping
    timeframe_map = {
        '1m': '1min',
        '2m': '2min',
        '3m': '3min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '1h',
        '4h': '4h'
    }

    if timeframe == '1m':
        return df  # Bereits 1-Minuten Daten

    freq = timeframe_map[timeframe]

    # OHLCV Aggregation
    aggregated = df.resample(freq).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()

    print(f"  {timeframe}: {len(aggregated)} Kerzen aggregiert")

    return aggregated

def split_by_months(df, year=2024):
    """Teilt DataFrame nach Monaten auf"""
    monthly_data = {}

    for month in range(1, 13):
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)

        month_data = df[(df.index >= month_start) & (df.index < month_end)]

        if len(month_data) > 0:
            month_name = month_start.strftime('%m')  # 01, 02, ..., 12
            monthly_data[month_name] = month_data
            print(f"  Monat {month_name}: {len(month_data)} Kerzen")

    return monthly_data

def create_directory_structure():
    """Erstellt die Verzeichnisstruktur für alle Timeframes"""
    base_dir = Path("src/data/aggregated")
    timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']

    for timeframe in timeframes:
        tf_dir = base_dir / timeframe
        tf_dir.mkdir(parents=True, exist_ok=True)
        print(f"Verzeichnis erstellt: {tf_dir}")

def save_monthly_data(timeframe, monthly_data):
    """Speichert monatliche Daten für einen Timeframe"""
    base_dir = Path("src/data/aggregated") / timeframe

    for month, data in monthly_data.items():
        filename = f"nq-2024-{month}.csv"
        filepath = base_dir / filename

        # Index zurück zu DateTime Spalten konvertieren
        data_to_save = data.reset_index()
        data_to_save['Date'] = data_to_save['datetime'].dt.strftime('%m/%d/%Y')
        data_to_save['Time'] = data_to_save['datetime'].dt.strftime('%H:%M:%S')

        # Spalten neu ordnen
        data_to_save = data_to_save[['Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume']]

        # CSV speichern
        data_to_save.to_csv(filepath, index=False)
        print(f"  Gespeichert: {filepath} ({len(data_to_save)} Kerzen)")

def create_yearly_aggregated_files():
    """Erstellt auch Jahres-CSV Dateien für Kompatibilität"""
    base_dir = Path("src/data/aggregated")
    timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']

    for timeframe in timeframes:
        tf_dir = base_dir / timeframe
        monthly_files = list(tf_dir.glob("nq-2024-*.csv"))

        if monthly_files:
            # Alle monatlichen Dateien kombinieren
            dfs = []
            for file in sorted(monthly_files):
                df = pd.read_csv(file)
                dfs.append(df)

            combined = pd.concat(dfs, ignore_index=True)

            # Jahres-Datei speichern
            yearly_file = tf_dir / "nq-2024.csv"
            combined.to_csv(yearly_file, index=False)
            print(f"Jahres-Datei erstellt: {yearly_file} ({len(combined)} Kerzen)")

def main():
    """Hauptfunktion - Kompletter Datenaufbau"""
    print("RL Trading - Datenaufbau gestartet")
    print("=" * 50)

    try:
        # Schritt 1: Quelldaten laden
        print("\n1. Lade 1-Minuten Quelldaten...")
        df_1m = load_source_data()

        # Schritt 2: Verzeichnisstruktur erstellen
        print("\n2. Erstelle Verzeichnisstruktur...")
        create_directory_structure()

        # Schritt 3: Alle Timeframes verarbeiten
        print("\n3. Aggregiere und speichere Timeframes...")
        timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']

        for timeframe in timeframes:
            print(f"\n  Verarbeite {timeframe}...")

            # Timeframe aggregieren
            df_aggregated = aggregate_timeframe(df_1m, timeframe)

            # Nach Monaten aufteilen
            monthly_data = split_by_months(df_aggregated)

            # Monatliche Dateien speichern
            save_monthly_data(timeframe, monthly_data)

        # Schritt 4: Jahres-Dateien für Kompatibilität erstellen
        print("\n4. Erstelle Jahres-Dateien...")
        create_yearly_aggregated_files()

        print("\n" + "=" * 50)
        print("ERFOLGREICH! Datenaufbau abgeschlossen.")
        print(f"Alle Timeframes in src/data/aggregated/ verfügbar")

        # Verzeichnisstruktur anzeigen
        print("\nErstellte Struktur:")
        base_dir = Path("src/data/aggregated")
        for tf_dir in sorted(base_dir.iterdir()):
            if tf_dir.is_dir():
                file_count = len(list(tf_dir.glob("*.csv")))
                print(f"  {tf_dir.name}/: {file_count} CSV Dateien")

    except Exception as e:
        print(f"\nFEHLER: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())