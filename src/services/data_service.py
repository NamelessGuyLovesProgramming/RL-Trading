"""
Data Service Layer für RL Trading App
Trennung der Business Logic von UI Components
Implementiert Repository Pattern und Data Processing Logic
"""

from typing import Dict, Any, Optional, List
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz

from data.yahoo_finance import get_yfinance_data
from config.settings import DEFAULT_SESSION_STATE


class DataService:
    """Service für alle Datenoperationen - Single Responsibility"""

    def __init__(self):
        # Timezone für alle Datenoperationen
        self.timezone = pytz.timezone('Europe/Berlin')

    def get_market_data(self, symbol: str = "NQ=F", period: str = "5d",
                       interval: str = "5m") -> Optional[Dict[str, Any]]:
        """
        Lädt Marktdaten für ein Symbol mit Error Handling

        Args:
            symbol: Trading Symbol (z.B. 'NQ=F')
            period: Zeitraum ('1d', '5d', '1mo', etc.)
            interval: Interval ('1m', '5m', '15m', etc.)

        Returns:
            Dict mit Marktdaten oder None bei Fehler
        """
        try:
            return get_yfinance_data(symbol, period, interval)
        except Exception as e:
            st.error(f"Fehler beim Laden der Daten für {symbol}: {str(e)}")
            return None

    def auto_load_default_asset(self) -> None:
        """
        Lädt Standard-Asset beim ersten App-Start
        Implementiert Open/Closed Principle - Symbol aus Config
        """
        if 'data_dict' not in st.session_state or not st.session_state['data_dict']:
            default_symbol = DEFAULT_SESSION_STATE['selected_symbol']
            default_interval = DEFAULT_SESSION_STATE['selected_interval']

            with st.spinner(f'⚡ Lade Standard-Asset {default_symbol}...'):
                data_dict = self.get_market_data(default_symbol, period="5d",
                                               interval=default_interval)
                if data_dict:
                    st.session_state['data_dict'] = data_dict
                    st.success(f'✅ {default_symbol} Daten geladen!')

    def refresh_data(self) -> bool:
        """
        Aktualisiert aktuelle Daten im Session State

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        if 'selected_symbol' in st.session_state and 'selected_interval' in st.session_state:
            symbol = st.session_state['selected_symbol']
            interval = st.session_state['selected_interval']

            with st.spinner(f'🔄 Aktualisiere {symbol} Daten...'):
                data_dict = self.get_market_data(symbol, period="5d", interval=interval)
                if data_dict:
                    st.session_state['data_dict'] = data_dict
                    st.success(f'✅ {symbol} Daten aktualisiert!')
                    return True
        return False

    def get_debug_data(self, symbol: str, days_back: int = 30,
                      interval: str = "5m") -> Optional[Dict[str, Any]]:
        """
        Lädt erweiterte Debug-Daten für historische Simulation

        Args:
            symbol: Trading Symbol
            days_back: Tage in die Vergangenheit
            interval: Zeitinterval

        Returns:
            Dict mit Debug-Daten oder None bei Fehler
        """
        return self.get_market_data(symbol, period=f"{days_back}d", interval=interval)

    def determine_chart_data(self) -> Optional[Dict[str, Any]]:
        """
        Bestimmt welche Daten für Chart verwendet werden sollen
        Berücksichtigt Debug-Modus und gefilterte Daten

        Returns:
            Chart-relevante Daten oder None
        """
        # Debug-Modus: Verwende gefilterte Daten basierend auf Startdatum und Index
        if st.session_state.get('debug_mode', False):
            from data.yahoo_finance import filter_debug_data

            debug_all_data = st.session_state.get('debug_all_data')
            debug_start_date = st.session_state.get('debug_start_date')
            debug_current_index = st.session_state.get('debug_current_index', 0)

            if debug_all_data and debug_start_date is not None:
                # Filtere Daten für aktuellen Debug-Stand
                filtered_data = filter_debug_data(
                    debug_all_data,
                    debug_start_date,
                    debug_current_index
                )
                return filtered_data

        # Fallback auf normale Live-Daten
        return st.session_state.get('live_data')

    def filter_debug_data_by_date(self, data_dict: Dict[str, Any],
                                 end_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Filtert Debug-Daten bis zu einem bestimmten Enddatum

        Args:
            data_dict: Originale Datenstruktur
            end_date: Enddatum für Filterung

        Returns:
            Gefilterte Datenstruktur
        """
        if not data_dict or 'df' not in data_dict:
            return None

        try:
            df = data_dict['df'].copy()

            # Zeitzone-bewusste Filterung
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC').tz_convert(self.timezone)
            else:
                df.index = df.index.tz_convert(self.timezone)

            # Enddatum timezone-aware machen
            if end_date.tzinfo is None:
                end_date = self.timezone.localize(end_date)
            else:
                end_date = end_date.astimezone(self.timezone)

            # Daten bis Enddatum filtern
            filtered_df = df[df.index <= end_date]

            if len(filtered_df) == 0:
                return None

            # Neue gefilterte Datenstruktur erstellen
            filtered_data = data_dict.copy()
            filtered_data['df'] = filtered_df
            filtered_data['symbol'] = data_dict['symbol']
            filtered_data['interval'] = data_dict['interval']

            return filtered_data

        except Exception as e:
            st.error(f"Fehler beim Filtern der Debug-Daten: {str(e)}")
            return None

    def get_latest_price(self, data_dict: Dict[str, Any]) -> Optional[float]:
        """
        Extrahiert den neuesten Preis aus den Marktdaten

        Args:
            data_dict: Marktdaten Dictionary

        Returns:
            Aktueller Close-Preis oder None
        """
        if not data_dict or 'df' not in data_dict:
            return None

        df = data_dict['df']
        if len(df) > 0:
            return float(df['Close'].iloc[-1])
        return None

    def validate_symbol(self, symbol: str) -> bool:
        """
        Validiert Trading Symbol Format

        Args:
            symbol: Trading Symbol zum validieren

        Returns:
            True wenn valide, False sonst
        """
        if not symbol or len(symbol.strip()) == 0:
            return False

        # Basis-Validierung für Trading Symbole
        symbol = symbol.strip().upper()
        return len(symbol) >= 2 and symbol.replace('=', '').replace('-', '').isalnum()