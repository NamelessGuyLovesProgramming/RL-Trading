"""
Unit Tests für DataService
Test-First Development für Data Layer Testing
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import pytz

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.data_service import DataService


class TestDataService(unittest.TestCase):
    """Test Cases für DataService"""

    def setUp(self):
        """Setup vor jedem Test"""
        self.data_service = DataService()

    @patch('services.data_service.get_yfinance_data')
    def test_get_market_data_success(self, mock_yfinance):
        """Test: Erfolgreiche Marktdaten-Abfrage"""
        # Arrange
        expected_data = {
            'df': pd.DataFrame({'Close': [15500.0, 15510.0]}),
            'symbol': 'NQ=F',
            'interval': '5m'
        }
        mock_yfinance.return_value = expected_data

        # Act
        result = self.data_service.get_market_data('NQ=F', '5d', '5m')

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result['symbol'], 'NQ=F')
        mock_yfinance.assert_called_once_with('NQ=F', '5d', '5m')

    @patch('services.data_service.get_yfinance_data')
    @patch('streamlit.error')
    def test_get_market_data_error_handling(self, mock_st_error, mock_yfinance):
        """Test: Error Handling bei Marktdaten-Abfrage"""
        # Arrange
        mock_yfinance.side_effect = Exception("API Error")

        # Act
        result = self.data_service.get_market_data('INVALID', '5d', '5m')

        # Assert
        self.assertIsNone(result)
        mock_st_error.assert_called_once()

    @patch('streamlit.session_state', new_callable=dict)
    @patch('streamlit.spinner')
    @patch('streamlit.success')
    def test_auto_load_default_asset(self, mock_success, mock_spinner, mock_session_state):
        """Test: Auto-Load des Standard-Assets"""
        # Arrange
        mock_session_state.update({
            'data_dict': None
        })

        with patch.object(self.data_service, 'get_market_data') as mock_get_data:
            mock_get_data.return_value = {'symbol': 'NQ=F', 'df': pd.DataFrame()}

            # Act
            self.data_service.auto_load_default_asset()

            # Assert
            mock_get_data.assert_called_once()
            mock_success.assert_called_once()

    @patch('streamlit.session_state', new_callable=dict)
    def test_refresh_data_success(self, mock_session_state):
        """Test: Erfolgreiche Daten-Aktualisierung"""
        # Arrange
        mock_session_state.update({
            'selected_symbol': 'NQ=F',
            'selected_interval': '5m'
        })

        with patch.object(self.data_service, 'get_market_data') as mock_get_data:
            mock_get_data.return_value = {'symbol': 'NQ=F'}

            with patch('streamlit.spinner'), patch('streamlit.success'):
                # Act
                result = self.data_service.refresh_data()

                # Assert
                self.assertTrue(result)
                self.assertEqual(mock_session_state['data_dict']['symbol'], 'NQ=F')

    def test_get_latest_price_success(self):
        """Test: Extraktion des neuesten Preises"""
        # Arrange
        df = pd.DataFrame({'Close': [15500.0, 15510.0, 15520.0]})
        data_dict = {'df': df, 'symbol': 'NQ=F'}

        # Act
        latest_price = self.data_service.get_latest_price(data_dict)

        # Assert
        self.assertEqual(latest_price, 15520.0)

    def test_get_latest_price_invalid_data(self):
        """Test: Handling von ungültigen Daten"""
        # Empty data
        self.assertIsNone(self.data_service.get_latest_price(None))
        self.assertIsNone(self.data_service.get_latest_price({}))

        # Empty DataFrame
        data_dict = {'df': pd.DataFrame()}
        self.assertIsNone(self.data_service.get_latest_price(data_dict))

    def test_validate_symbol(self):
        """Test: Symbol-Validierung"""
        # Valid symbols
        self.assertTrue(self.data_service.validate_symbol('NQ=F'))
        self.assertTrue(self.data_service.validate_symbol('AAPL'))
        self.assertTrue(self.data_service.validate_symbol('BTC-USD'))

        # Invalid symbols
        self.assertFalse(self.data_service.validate_symbol(''))
        self.assertFalse(self.data_service.validate_symbol('   '))
        self.assertFalse(self.data_service.validate_symbol('A'))

    @patch('streamlit.session_state', new_callable=dict)
    def test_determine_chart_data_debug_mode(self, mock_session_state):
        """Test: Chart-Daten Bestimmung im Debug-Modus"""
        # Arrange
        debug_data = {'df': pd.DataFrame(), 'symbol': 'DEBUG'}
        live_data = {'df': pd.DataFrame(), 'symbol': 'LIVE'}

        mock_session_state.update({
            'debug_filtered_data': debug_data,
            'debug_mode': True,
            'data_dict': live_data
        })

        # Act
        result = self.data_service.determine_chart_data()

        # Assert
        self.assertEqual(result['symbol'], 'DEBUG')

    @patch('streamlit.session_state', new_callable=dict)
    def test_determine_chart_data_live_mode(self, mock_session_state):
        """Test: Chart-Daten Bestimmung im Live-Modus"""
        # Arrange
        live_data = {'df': pd.DataFrame(), 'symbol': 'LIVE'}

        mock_session_state.update({
            'debug_filtered_data': None,
            'debug_mode': False,
            'data_dict': live_data
        })

        # Act
        result = self.data_service.determine_chart_data()

        # Assert
        self.assertEqual(result['symbol'], 'LIVE')

    def test_filter_debug_data_by_date(self):
        """Test: Debug-Daten Filterung nach Datum"""
        # Arrange
        berlin_tz = pytz.timezone('Europe/Berlin')
        dates = pd.date_range('2023-01-01', periods=5, freq='D', tz=berlin_tz)
        df = pd.DataFrame({'Close': [100, 101, 102, 103, 104]}, index=dates)
        data_dict = {'df': df, 'symbol': 'TEST'}

        end_date = datetime(2023, 1, 3, tzinfo=berlin_tz)

        # Act
        filtered_data = self.data_service.filter_debug_data_by_date(data_dict, end_date)

        # Assert
        self.assertIsNotNone(filtered_data)
        self.assertEqual(len(filtered_data['df']), 3)  # Bis zum 3. Januar
        self.assertEqual(filtered_data['symbol'], 'TEST')

    @patch('streamlit.error')
    def test_filter_debug_data_error_handling(self, mock_error):
        """Test: Error Handling bei Debug-Daten Filterung"""
        # Invalid data
        result = self.data_service.filter_debug_data_by_date(None, datetime.now())
        self.assertIsNone(result)

        result = self.data_service.filter_debug_data_by_date({}, datetime.now())
        self.assertIsNone(result)


if __name__ == '__main__':
    # Streamlit Mock für Tests
    sys.modules['streamlit'] = MagicMock()

    unittest.main()