"""
Unit Tests für TradingService
Test-First Development für bessere Code-Qualität
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import pytz

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.trading_service import TradingService


class TestTradingService(unittest.TestCase):
    """Test Cases für TradingService"""

    def setUp(self):
        """Setup vor jedem Test"""
        self.trading_service = TradingService()

    @patch('streamlit.session_state', new_callable=dict)
    def test_add_trade_success(self, mock_session_state):
        """Test: Erfolgreiche Trade-Erstellung"""
        # Arrange
        mock_session_state.update({
            'trades': [],
            'selected_symbol': 'NQ=F'
        })

        # Act
        result = self.trading_service.add_trade('BUY', 15500.0, 'Manual')

        # Assert
        self.assertTrue(result)
        self.assertEqual(len(mock_session_state['trades']), 1)

        trade = mock_session_state['trades'][0]
        self.assertEqual(trade['action'], 'BUY')
        self.assertEqual(trade['price'], 15500.0)
        self.assertEqual(trade['source'], 'Manual')
        self.assertEqual(trade['symbol'], 'NQ=F')

    @patch('streamlit.session_state', new_callable=dict)
    def test_add_trade_validation_failure(self, mock_session_state):
        """Test: Trade-Validierung schlägt fehl"""
        # Arrange
        mock_session_state.update({
            'trades': [],
            'selected_symbol': 'NQ=F'
        })

        # Act & Assert - Ungültige Action
        with patch('streamlit.error'):
            result = self.trading_service.add_trade('INVALID', 15500.0, 'Manual')
            self.assertFalse(result)

        # Act & Assert - Negativer Preis
        with patch('streamlit.error'):
            result = self.trading_service.add_trade('BUY', -100.0, 'Manual')
            self.assertFalse(result)

        # Act & Assert - Null Quantity
        with patch('streamlit.error'):
            result = self.trading_service.add_trade('BUY', 15500.0, 'Manual', quantity=0)
            self.assertFalse(result)

    @patch('streamlit.session_state', new_callable=dict)
    def test_get_current_position(self, mock_session_state):
        """Test: Berechnung der aktuellen Position"""
        # Arrange
        mock_session_state.update({
            'trades': [
                {'action': 'BUY', 'quantity': 2, 'symbol': 'NQ=F'},
                {'action': 'BUY', 'quantity': 1, 'symbol': 'NQ=F'},
                {'action': 'SELL', 'quantity': 1, 'symbol': 'NQ=F'},
            ],
            'selected_symbol': 'NQ=F'
        })

        # Act
        position = self.trading_service.get_current_position('NQ=F')

        # Assert
        self.assertEqual(position, 2)  # 3 BUY - 1 SELL = 2

    @patch('streamlit.session_state', new_callable=dict)
    def test_calculate_unrealized_pnl(self, mock_session_state):
        """Test: Unrealisierter PnL Berechnung"""
        # Arrange
        mock_session_state.update({
            'trades': [
                {'action': 'BUY', 'quantity': 1, 'symbol': 'NQ=F', 'price': 15000.0},
                {'action': 'BUY', 'quantity': 1, 'symbol': 'NQ=F', 'price': 15100.0},
            ],
            'selected_symbol': 'NQ=F'
        })

        # Act
        unrealized_pnl = self.trading_service.calculate_unrealized_pnl(15200.0, 'NQ=F')

        # Assert
        # Position: 2, Avg Entry: 15050.0, Current: 15200.0
        # PnL = 2 * (15200 - 15050) = 300.0
        self.assertEqual(unrealized_pnl, 300.0)

    @patch('streamlit.session_state', new_callable=dict)
    def test_get_trading_statistics(self, mock_session_state):
        """Test: Trading-Statistiken Berechnung"""
        # Arrange
        mock_session_state.update({
            'trades': [
                {'action': 'BUY', 'quantity': 1, 'symbol': 'NQ=F', 'price': 15000.0},
                {'action': 'BUY', 'quantity': 2, 'symbol': 'NQ=F', 'price': 15100.0},
                {'action': 'SELL', 'quantity': 1, 'symbol': 'NQ=F', 'price': 15200.0},
            ],
            'selected_symbol': 'NQ=F'
        })

        # Act
        stats = self.trading_service.get_trading_statistics('NQ=F')

        # Assert
        self.assertEqual(stats['total_trades'], 3)
        self.assertEqual(stats['buy_trades'], 2)
        self.assertEqual(stats['sell_trades'], 1)
        self.assertEqual(stats['buy_volume'], 3)
        self.assertEqual(stats['sell_volume'], 1)
        self.assertEqual(stats['current_position'], 2)

    @patch('streamlit.session_state', new_callable=dict)
    def test_close_all_positions(self, mock_session_state):
        """Test: Alle Positionen schließen"""
        # Arrange
        mock_session_state.update({
            'trades': [
                {'action': 'BUY', 'quantity': 3, 'symbol': 'NQ=F', 'price': 15000.0},
            ],
            'selected_symbol': 'NQ=F'
        })

        with patch('streamlit.success'):
            # Act
            result = self.trading_service.close_all_positions(15500.0, 'NQ=F')

            # Assert
            self.assertTrue(result)
            self.assertEqual(len(mock_session_state['trades']), 2)

            close_trade = mock_session_state['trades'][1]
            self.assertEqual(close_trade['action'], 'SELL')
            self.assertEqual(close_trade['quantity'], 3)
            self.assertEqual(close_trade['source'], 'Auto Close')

    def test_validate_symbol(self):
        """Test: Symbol-Validierung"""
        # Valid symbols
        self.assertTrue(self.trading_service._validate_trade_input('BUY', 100.0, 1))

        # Invalid symbols
        with patch('streamlit.error'):
            self.assertFalse(self.trading_service._validate_trade_input('INVALID', 100.0, 1))
            self.assertFalse(self.trading_service._validate_trade_input('BUY', -100.0, 1))
            self.assertFalse(self.trading_service._validate_trade_input('BUY', 100.0, 0))


if __name__ == '__main__':
    # Streamlit Mock für Tests
    sys.modules['streamlit'] = MagicMock()

    unittest.main()