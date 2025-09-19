"""
Chart Service für FastAPI Integration
Kommunikation zwischen Streamlit und FastAPI Chart Server
"""

import requests
import json
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime


class ChartService:
    """Service für Communication mit FastAPI Chart Server"""

    def __init__(self, chart_server_url: str = "http://localhost:8001"):
        self.base_url = chart_server_url
        self.session = requests.Session()
        # Timeout für API Calls
        self.timeout = 5

    def set_chart_data(self, data: List[Dict], symbol: str = "NQ=F", interval: str = "5m") -> bool:
        """
        Sendet initiale Chart-Daten an FastAPI Server

        Args:
            data: Chart-Daten im TradingView Format
            symbol: Trading Symbol
            interval: Zeitintervall

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            payload = {
                "data": data,
                "symbol": symbol,
                "interval": interval
            }

            response = self.session.post(
                f"{self.base_url}/api/chart/set_data",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                logging.info(f"Chart data sent successfully: {len(data)} candles")
                return True
            else:
                logging.error(f"Failed to set chart data: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending chart data: {e}")
            return False

    def add_candle(self, candle: Dict[str, Any]) -> bool:
        """
        Fügt neue Kerze zum Chart hinzu

        Args:
            candle: Kerzen-Daten im TradingView Format
                   {'time': timestamp, 'open': float, 'high': float, 'low': float, 'close': float}

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            payload = {"candle": candle}

            response = self.session.post(
                f"{self.base_url}/api/chart/add_candle",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                logging.info(f"Candle added: {candle.get('time', 'unknown')} - {candle.get('close', 'N/A')}")
                return True
            else:
                logging.error(f"Failed to add candle: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Error adding candle: {e}")
            return False

    def get_chart_status(self) -> Optional[Dict[str, Any]]:
        """
        Holt Chart-Status vom FastAPI Server

        Returns:
            Status-Dictionary oder None bei Fehler
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/chart/status",
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Failed to get chart status: {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Error getting chart status: {e}")
            return None

    def is_server_running(self) -> bool:
        """
        Prüft ob FastAPI Chart Server läuft

        Returns:
            True wenn Server erreichbar, False sonst
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/chart/status",
                timeout=2  # Kurzer Timeout für Connectivity Check
            )
            return response.status_code == 200

        except requests.exceptions.RequestException:
            return False

    def convert_dataframe_to_chart_data(self, df) -> List[Dict[str, Any]]:
        """
        Konvertiert pandas DataFrame zu TradingView Chart Format

        Args:
            df: DataFrame mit OHLCV Daten

        Returns:
            Liste von Chart-Daten Dictionaries
        """
        chart_data = []

        for idx, row in df.iterrows():
            chart_data.append({
                'time': int(idx.timestamp()),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close'])
            })

        return chart_data

    def create_candle_from_row(self, row, timestamp) -> Dict[str, Any]:
        """
        Erstellt Kerzen-Daten aus DataFrame Row

        Args:
            row: DataFrame Row mit OHLC Daten
            timestamp: Timestamp für die Kerze

        Returns:
            Kerzen-Dictionary im TradingView Format
        """
        return {
            'time': int(timestamp.timestamp()),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close'])
        }

    def add_position_overlay(self, position: Dict[str, Any]) -> bool:
        """
        Fügt Position Overlay zum Chart hinzu

        Args:
            position: Position-Daten mit SL/TP

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            payload = {"position": position}

            response = self.session.post(
                f"{self.base_url}/api/chart/add_position",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                logging.info(f"Position overlay added: {position.get('id', 'unknown')}")
                return True
            else:
                logging.error(f"Failed to add position overlay: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Error adding position overlay: {e}")
            return False

    def remove_position_overlay(self, position_id: str) -> bool:
        """
        Entfernt Position Overlay vom Chart

        Args:
            position_id: ID der zu entfernenden Position

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            payload = {"position_id": position_id}

            response = self.session.post(
                f"{self.base_url}/api/chart/remove_position",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                logging.info(f"Position overlay removed: {position_id}")
                return True
            else:
                logging.error(f"Failed to remove position overlay: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Error removing position overlay: {e}")
            return False

    def sync_positions(self, positions: List[Dict[str, Any]]) -> bool:
        """
        Synchronisiert alle Positionen mit dem Chart

        Args:
            positions: Liste aller aktiven Positionen

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            payload = {"positions": positions}

            response = self.session.post(
                f"{self.base_url}/api/chart/sync_positions",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                logging.info(f"Positions synchronized: {len(positions)} positions")
                return True
            else:
                logging.error(f"Failed to sync positions: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logging.error(f"Error syncing positions: {e}")
            return False


def get_chart_service() -> ChartService:
    """Factory-Funktion für ChartService Singleton"""
    if not hasattr(get_chart_service, '_instance'):
        get_chart_service._instance = ChartService()
    return get_chart_service._instance