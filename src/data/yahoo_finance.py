"""
Yahoo Finance Daten-Integration
Zentrale Schnittstelle für das Laden von Marktdaten über yfinance
"""

import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime
import streamlit as st
from config.settings import DATA_CONFIG

def _make_timezone_compatible(start_datetime, df_index):
    """
    Macht start_datetime kompatibel mit dem DataFrame Index für Vergleiche

    Args:
        start_datetime: datetime object
        df_index: pandas DatetimeIndex

    Returns:
        timezone-kompatibles datetime object
    """
    if df_index.tz is not None and start_datetime.tzinfo is None:
        # DataFrame hat Timezone, start_datetime nicht - lokalisiere start_datetime
        return start_datetime.replace(tzinfo=df_index.tz)
    elif df_index.tz is None and start_datetime.tzinfo is not None:
        # DataFrame hat keine Timezone, start_datetime schon - entferne Timezone
        return start_datetime.replace(tzinfo=None)
    else:
        # Beide haben gleiche Timezone-Situation
        return start_datetime

def get_yfinance_data(symbol, period="1d", interval="5m"):
    """
    Lädt Live-Daten von Yahoo Finance mit automatischer Zeitzone-Konvertierung

    Args:
        symbol (str): Trading Symbol (z.B. "NQ=F", "AAPL")
        period (str): Zeitraum ("1d", "5d", "30d", "1y")
        interval (str): Intervall ("1m", "5m", "15m", "1h", "1d")

    Returns:
        dict: Daten-Dictionary mit 'data', 'current_price', 'symbol', 'last_update', 'info'
        None: Bei Fehlern
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            st.error(f"Keine Daten für Symbol {symbol} verfügbar")
            return None

        # Timezone handling für TradingView - UTC+2 (Europa/Berlin)
        hist = _convert_timezone(hist, DATA_CONFIG['timezone'])

        # Runde Preise auf 2 Dezimalstellen
        hist = hist.round(2)

        # Hole zusätzliche Ticker-Informationen
        info = ticker.info
        current_price = info.get('currentPrice', hist['Close'].iloc[-1])

        return {
            'data': hist,
            'current_price': current_price,
            'symbol': symbol,
            'last_update': datetime.now(),
            'info': info
        }

    except Exception as e:
        st.error(f"Fehler beim Laden von {symbol}: {e}")
        return None

def _convert_timezone(hist, target_timezone):
    """
    Konvertiert Daten-Index zur gewünschten Zeitzone

    Args:
        hist (DataFrame): Historische Daten von yfinance
        target_timezone (str): Ziel-Zeitzone (z.B. 'Europe/Berlin')

    Returns:
        DataFrame: Daten mit konvertierter Zeitzone
    """
    if hist.index.tz is not None:
        # Zeitzone ist bereits gesetzt, konvertiere zu Ziel-Zeitzone
        hist.index = hist.index.tz_convert(target_timezone).tz_localize(None)
    else:
        # Keine Zeitzone gesetzt, füge Ziel-Zeitzone hinzu
        target_tz = pytz.timezone(target_timezone)
        hist.index = hist.index.tz_localize('UTC').tz_convert(target_tz).tz_localize(None)

    return hist

def filter_debug_data(data_dict, debug_start_date, current_index):
    """
    Filtert Daten für Debug-Modus bis zum aktuellen Index.
    Zeigt alle Daten und iteriert ab dem Startdatum bis heute.

    Args:
        data_dict (dict): Vollständige Daten
        debug_start_date (date): Start-Datum für Debug-Iteration
        current_index (int): Aktueller Kerzen-Index (relativ zum Startdatum)

    Returns:
        dict: Gefilterte Daten oder None
    """
    if not data_dict or data_dict['data'].empty:
        return None

    df = data_dict['data'].copy()

    # Konvertiere debug_start_date zu datetime falls nötig
    if hasattr(debug_start_date, 'date'):
        start_datetime = debug_start_date
    else:
        start_datetime = datetime.combine(debug_start_date, datetime.min.time())

    # Timezone-Handling für korrekte Vergleiche
    start_datetime = _make_timezone_compatible(start_datetime, df.index)

    # Finde den Index des Startdatums in den Originaldaten
    start_index = None
    for i, timestamp in enumerate(df.index):
        if timestamp >= start_datetime:
            start_index = i
            break

    if start_index is None:
        # Startdatum liegt nach allen verfügbaren Daten
        return None

    # Berechne den absoluten Index: Startdatum-Index + aktueller Debug-Index
    absolute_index = start_index + current_index

    # Nehme alle Daten bis zum absoluten Index
    if absolute_index < len(df):
        df_filtered = df.iloc[:absolute_index + 1]
    else:
        # Falls über die verfügbaren Daten hinaus, nimm alle
        df_filtered = df

    # Erstelle neues data_dict mit gefilterten Daten
    filtered_data = {
        'data': df_filtered,
        'current_price': df_filtered['Close'].iloc[-1] if not df_filtered.empty else 0,
        'symbol': data_dict['symbol'],
        'last_update': data_dict['last_update'],
        'info': data_dict['info'],
        'debug_start_index': start_index,  # Zusätzliche Info für Chart-Positionierung
        'debug_current_timestamp': df_filtered.index[-1] if not df_filtered.empty else None
    }

    return filtered_data

def get_debug_data(symbol, interval="5m"):
    """
    Lädt erweiterte historische Daten für Debug-Modus (30 Tage)

    Args:
        symbol (str): Trading Symbol
        interval (str): Intervall

    Returns:
        dict: Erweiterte historische Daten
    """
    return get_yfinance_data(
        symbol,
        period=DATA_CONFIG['debug_period'],
        interval=interval
    )

def validate_data_integrity(data_dict):
    """
    Prüft die Integrität der geladenen Daten

    Args:
        data_dict (dict): Daten-Dictionary

    Returns:
        bool: True wenn Daten gültig sind
    """
    if not data_dict:
        return False

    required_keys = ['data', 'current_price', 'symbol', 'last_update']
    if not all(key in data_dict for key in required_keys):
        return False

    if data_dict['data'].empty:
        return False

    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in data_dict['data'].columns for col in required_columns):
        return False

    return True