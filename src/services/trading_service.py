"""
Trading Service Layer für RL Trading App
Business Logic für Trading-Operationen und Portfolio Management
Implementiert Command Pattern und Strategy Pattern für erweiterbare Trading Logic
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
import pytz


class TradingService:
    """Service für alle Trading-Operationen - Single Responsibility"""

    def __init__(self):
        # Timezone für alle Trading-Operationen
        self.timezone = pytz.timezone('Europe/Berlin')

        # Position Management
        self._init_position_management()

    def add_trade(self, action: str, price: float, source: str = 'Manual',
                 quantity: int = 1, symbol: str = None) -> bool:
        """
        Fügt einen neuen Trade hinzu mit vollständiger Validierung
        Implementiert Command Pattern für Trading Actions

        Args:
            action: 'BUY' oder 'SELL'
            price: Trade-Preis
            source: Quelle des Trades ('Manual', 'Auto', 'RL')
            quantity: Anzahl der Kontrakte
            symbol: Trading Symbol (optional, aus Session State wenn nicht gegeben)

        Returns:
            True wenn Trade erfolgreich hinzugefügt, False bei Fehler
        """
        # Input Validation
        if not self._validate_trade_input(action, price, quantity):
            return False

        # Symbol aus Session State wenn nicht gegeben
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', 'UNKNOWN')

        # Trades Container initialisieren
        if 'trades' not in st.session_state:
            st.session_state['trades'] = []

        # Neuen Trade erstellen
        trade = {
            'timestamp': datetime.now(self.timezone),
            'action': action.upper(),
            'price': float(price),
            'quantity': int(quantity),
            'symbol': symbol,
            'source': source,
            'pnl': 0.0  # Wird bei Close-Trades berechnet
        }

        # Trade hinzufügen
        st.session_state['trades'].append(trade)

        # Portfolio-Statistiken aktualisieren
        self._update_portfolio_stats()

        st.success(f'✅ Trade hinzugefügt: {action} {quantity}x {symbol} @ {price:.2f} ({source})')
        return True

    def get_current_position(self, symbol: str = None) -> int:
        """
        Berechnet aktuelle Netto-Position für ein Symbol

        Args:
            symbol: Trading Symbol (optional, aus Session State wenn nicht gegeben)

        Returns:
            Netto-Position (positiv = long, negativ = short, 0 = flat)
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        if 'trades' not in st.session_state:
            return 0

        position = 0
        for trade in st.session_state['trades']:
            if trade['symbol'] == symbol:
                if trade['action'] == 'BUY':
                    position += trade['quantity']
                elif trade['action'] == 'SELL':
                    position -= trade['quantity']

        return position

    def calculate_unrealized_pnl(self, current_price: float, symbol: str = None) -> float:
        """
        Berechnet unrealisierten PnL für aktuelle Position

        Args:
            current_price: Aktueller Marktpreis
            symbol: Trading Symbol

        Returns:
            Unrealisierter PnL in Währungseinheiten
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        position = self.get_current_position(symbol)
        if position == 0:
            return 0.0

        # Durchschnittlicher Entry-Preis berechnen
        avg_entry_price = self._calculate_average_entry_price(symbol)
        if avg_entry_price is None:
            return 0.0

        # PnL = Position × (Current Price - Avg Entry Price)
        unrealized_pnl = position * (current_price - avg_entry_price)
        return unrealized_pnl

    def calculate_realized_pnl(self, symbol: str = None) -> float:
        """
        Berechnet realisierten PnL aus abgeschlossenen Trades

        Args:
            symbol: Trading Symbol

        Returns:
            Realisierter PnL in Währungseinheiten
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        if 'trades' not in st.session_state:
            return 0.0

        # Vereinfachte Berechnung: FIFO (First In, First Out)
        return self._calculate_fifo_pnl(symbol)

    def get_trading_statistics(self, symbol: str = None) -> Dict[str, Any]:
        """
        Berechnet umfassende Trading-Statistiken

        Args:
            symbol: Trading Symbol

        Returns:
            Dictionary mit Trading-Statistiken
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        if 'trades' not in st.session_state:
            return self._empty_stats()

        symbol_trades = [t for t in st.session_state['trades'] if t['symbol'] == symbol]

        if not symbol_trades:
            return self._empty_stats()

        # Basis-Statistiken
        total_trades = len(symbol_trades)
        buy_trades = len([t for t in symbol_trades if t['action'] == 'BUY'])
        sell_trades = len([t for t in symbol_trades if t['action'] == 'SELL'])

        # Volumen-Statistiken
        total_volume = sum(t['quantity'] for t in symbol_trades)
        buy_volume = sum(t['quantity'] for t in symbol_trades if t['action'] == 'BUY')
        sell_volume = sum(t['quantity'] for t in symbol_trades if t['action'] == 'SELL')

        # PnL-Statistiken
        realized_pnl = self.calculate_realized_pnl(symbol)
        current_position = self.get_current_position(symbol)

        return {
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'total_volume': total_volume,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'realized_pnl': realized_pnl,
            'current_position': current_position,
            'net_position': current_position,
            'avg_trade_size': total_volume / total_trades if total_trades > 0 else 0
        }

    def close_all_positions(self, current_price: float, symbol: str = None) -> bool:
        """
        Schließt alle offenen Positionen zum aktuellen Marktpreis

        Args:
            current_price: Aktueller Marktpreis zum Schließen
            symbol: Trading Symbol

        Returns:
            True wenn erfolgreich geschlossen, False bei Fehler
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        current_position = self.get_current_position(symbol)

        if current_position == 0:
            st.info("📊 Keine offenen Positionen zum Schließen")
            return True

        # Position schließen durch entgegengesetzte Order
        close_action = 'SELL' if current_position > 0 else 'BUY'
        quantity = abs(current_position)

        success = self.add_trade(
            action=close_action,
            price=current_price,
            source='Auto Close',
            quantity=quantity,
            symbol=symbol
        )

        if success:
            st.success(f'✅ Alle Positionen geschlossen: {close_action} {quantity}x @ {current_price:.2f}')

        return success

    def open_long_position(self, entry_price: float, quantity: int = 1,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None,
                          symbol: str = None) -> bool:
        """
        Öffnet eine Long-Position mit optionalem SL/TP

        Args:
            entry_price: Entry-Preis für die Position
            quantity: Anzahl der Kontrakte
            stop_loss: Stop Loss Preis (optional)
            take_profit: Take Profit Preis (optional)
            symbol: Trading Symbol

        Returns:
            True wenn Position erfolgreich eröffnet
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        # Validierung
        if stop_loss and stop_loss >= entry_price:
            st.error("❌ Stop Loss muss unter dem Entry-Preis liegen (Long)")
            return False

        if take_profit and take_profit <= entry_price:
            st.error("❌ Take Profit muss über dem Entry-Preis liegen (Long)")
            return False

        # Buy Trade hinzufügen
        success = self.add_trade('BUY', entry_price, 'Long Position', quantity, symbol)

        if success and (stop_loss or take_profit):
            # Position mit SL/TP zu aktiven Positionen hinzufügen
            position_data = {
                'id': self._generate_position_id(),
                'type': 'LONG',
                'entry_price': entry_price,
                'quantity': quantity,
                'symbol': symbol,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(self.timezone),
                'status': 'OPEN'
            }

            self._add_active_position(position_data)

            # Chart Overlay hinzufügen
            self._add_position_to_chart(position_data)

            st.success(f"🟢 Long Position eröffnet: {quantity}x {symbol} @ {entry_price:.2f}")
            if stop_loss:
                st.info(f"🛡️ Stop Loss: {stop_loss:.2f}")
            if take_profit:
                st.info(f"🎯 Take Profit: {take_profit:.2f}")

        return success

    def open_short_position(self, entry_price: float, quantity: int = 1,
                           stop_loss: Optional[float] = None,
                           take_profit: Optional[float] = None,
                           symbol: str = None) -> bool:
        """
        Öffnet eine Short-Position mit optionalem SL/TP

        Args:
            entry_price: Entry-Preis für die Position
            quantity: Anzahl der Kontrakte
            stop_loss: Stop Loss Preis (optional)
            take_profit: Take Profit Preis (optional)
            symbol: Trading Symbol

        Returns:
            True wenn Position erfolgreich eröffnet
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        # Validierung
        if stop_loss and stop_loss <= entry_price:
            st.error("❌ Stop Loss muss über dem Entry-Preis liegen (Short)")
            return False

        if take_profit and take_profit >= entry_price:
            st.error("❌ Take Profit muss unter dem Entry-Preis liegen (Short)")
            return False

        # Sell Trade hinzufügen
        success = self.add_trade('SELL', entry_price, 'Short Position', quantity, symbol)

        if success and (stop_loss or take_profit):
            # Position mit SL/TP zu aktiven Positionen hinzufügen
            position_data = {
                'id': self._generate_position_id(),
                'type': 'SHORT',
                'entry_price': entry_price,
                'quantity': quantity,
                'symbol': symbol,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(self.timezone),
                'status': 'OPEN'
            }

            self._add_active_position(position_data)

            # Chart Overlay hinzufügen
            self._add_position_to_chart(position_data)

            st.success(f"🔴 Short Position eröffnet: {quantity}x {symbol} @ {entry_price:.2f}")
            if stop_loss:
                st.info(f"🛡️ Stop Loss: {stop_loss:.2f}")
            if take_profit:
                st.info(f"🎯 Take Profit: {take_profit:.2f}")

        return success

    def get_active_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        Gibt alle aktiven Positionen zurück

        Args:
            symbol: Filter nach Symbol (optional)

        Returns:
            Liste der aktiven Positionen
        """
        if 'active_positions' not in st.session_state:
            return []

        positions = st.session_state['active_positions']

        if symbol:
            positions = [p for p in positions if p['symbol'] == symbol and p['status'] == 'OPEN']
        else:
            positions = [p for p in positions if p['status'] == 'OPEN']

        return positions

    def check_stop_loss_take_profit(self, current_price: float, symbol: str = None) -> List[str]:
        """
        Prüft alle aktiven Positionen auf SL/TP Trigger

        Args:
            current_price: Aktueller Marktpreis
            symbol: Trading Symbol

        Returns:
            Liste der ausgeführten Orders (für Logging)
        """
        if symbol is None:
            symbol = st.session_state.get('selected_symbol', '')

        executed_orders = []
        active_positions = self.get_active_positions(symbol)

        for position in active_positions:
            position_id = position['id']
            entry_price = position['entry_price']
            quantity = position['quantity']
            pos_type = position['type']

            # Long Position Checks
            if pos_type == 'LONG':
                # Stop Loss Check
                if position['stop_loss'] and current_price <= position['stop_loss']:
                    # Stop Loss getriggert
                    self.add_trade('SELL', current_price, f'SL-{position_id}', quantity, symbol)
                    self._close_position(position_id, current_price, 'STOP_LOSS')
                    self._remove_position_from_chart(position_id)
                    executed_orders.append(f"🛡️ SL Long: {quantity}x @ {current_price:.2f}")

                # Take Profit Check
                elif position['take_profit'] and current_price >= position['take_profit']:
                    # Take Profit getriggert
                    self.add_trade('SELL', current_price, f'TP-{position_id}', quantity, symbol)
                    self._close_position(position_id, current_price, 'TAKE_PROFIT')
                    self._remove_position_from_chart(position_id)
                    executed_orders.append(f"🎯 TP Long: {quantity}x @ {current_price:.2f}")

            # Short Position Checks
            elif pos_type == 'SHORT':
                # Stop Loss Check
                if position['stop_loss'] and current_price >= position['stop_loss']:
                    # Stop Loss getriggert
                    self.add_trade('BUY', current_price, f'SL-{position_id}', quantity, symbol)
                    self._close_position(position_id, current_price, 'STOP_LOSS')
                    self._remove_position_from_chart(position_id)
                    executed_orders.append(f"🛡️ SL Short: {quantity}x @ {current_price:.2f}")

                # Take Profit Check
                elif position['take_profit'] and current_price <= position['take_profit']:
                    # Take Profit getriggert
                    self.add_trade('BUY', current_price, f'TP-{position_id}', quantity, symbol)
                    self._close_position(position_id, current_price, 'TAKE_PROFIT')
                    self._remove_position_from_chart(position_id)
                    executed_orders.append(f"🎯 TP Short: {quantity}x @ {current_price:.2f}")

        return executed_orders

    def close_position_by_id(self, position_id: str, current_price: float) -> bool:
        """
        Schließt eine spezifische Position manuell

        Args:
            position_id: ID der zu schließenden Position
            current_price: Aktueller Marktpreis

        Returns:
            True wenn erfolgreich geschlossen
        """
        active_positions = self.get_active_positions()
        position = next((p for p in active_positions if p['id'] == position_id), None)

        if not position:
            st.error(f"❌ Position {position_id} nicht gefunden")
            return False

        # Entgegengesetzte Order
        close_action = 'SELL' if position['type'] == 'LONG' else 'BUY'
        quantity = position['quantity']
        symbol = position['symbol']

        success = self.add_trade(close_action, current_price, f'Manual-{position_id}', quantity, symbol)

        if success:
            self._close_position(position_id, current_price, 'MANUAL')
            # Chart Overlay entfernen
            self._remove_position_from_chart(position_id)
            st.success(f"✅ Position {position_id} manuell geschlossen @ {current_price:.2f}")

        return success

    def _init_position_management(self) -> None:
        """Initialisiert Position Management im Session State"""
        if 'active_positions' not in st.session_state:
            st.session_state['active_positions'] = []

        if 'position_counter' not in st.session_state:
            st.session_state['position_counter'] = 0

    def _generate_position_id(self) -> str:
        """Generiert eindeutige Position ID"""
        st.session_state['position_counter'] += 1
        return f"POS{st.session_state['position_counter']:04d}"

    def _add_active_position(self, position: Dict[str, Any]) -> None:
        """Fügt Position zu aktiven Positionen hinzu"""
        if 'active_positions' not in st.session_state:
            st.session_state['active_positions'] = []

        st.session_state['active_positions'].append(position)

    def _close_position(self, position_id: str, close_price: float, reason: str) -> None:
        """Markiert Position als geschlossen"""
        if 'active_positions' not in st.session_state:
            return

        for position in st.session_state['active_positions']:
            if position['id'] == position_id and position['status'] == 'OPEN':
                position['status'] = 'CLOSED'
                position['close_price'] = close_price
                position['close_reason'] = reason
                position['close_timestamp'] = datetime.now(self.timezone)
                break

    def _add_position_to_chart(self, position: Dict[str, Any]) -> None:
        """Fügt Position Overlay zum Chart hinzu"""
        try:
            from services.chart_service import get_chart_service
            chart_service = get_chart_service()

            # Konvertiere datetime zu ISO String für JSON Serialization
            position_data = position.copy()
            if 'timestamp' in position_data:
                position_data['timestamp'] = position_data['timestamp'].isoformat()

            chart_service.add_position_overlay(position_data)
        except Exception as e:
            # Nicht kritisch - Chart läuft weiter ohne Overlay
            pass

    def _remove_position_from_chart(self, position_id: str) -> None:
        """Entfernt Position Overlay vom Chart"""
        try:
            from services.chart_service import get_chart_service
            chart_service = get_chart_service()
            chart_service.remove_position_overlay(position_id)
        except Exception as e:
            # Nicht kritisch - Chart läuft weiter
            pass

    def _validate_trade_input(self, action: str, price: float, quantity: int) -> bool:
        """Validiert Trade-Input Parameter"""
        if action.upper() not in ['BUY', 'SELL']:
            st.error("❌ Ungültige Aktion. Nur 'BUY' oder 'SELL' erlaubt.")
            return False

        if price <= 0:
            st.error("❌ Preis muss größer als 0 sein.")
            return False

        if quantity <= 0:
            st.error("❌ Quantität muss größer als 0 sein.")
            return False

        return True

    def _calculate_average_entry_price(self, symbol: str) -> Optional[float]:
        """Berechnet durchschnittlichen Entry-Preis für aktuelle Position"""
        if 'trades' not in st.session_state:
            return None

        # Vereinfachte Berechnung: Weighted Average der noch offenen Positionen
        symbol_trades = [t for t in st.session_state['trades'] if t['symbol'] == symbol]

        if not symbol_trades:
            return None

        # FIFO-Simulation zur Bestimmung des aktuellen Entry-Preises
        running_position = 0
        total_cost = 0.0

        for trade in symbol_trades:
            if trade['action'] == 'BUY':
                running_position += trade['quantity']
                total_cost += trade['quantity'] * trade['price']
            elif trade['action'] == 'SELL':
                if running_position > 0:
                    # Anteilige Kosten reduzieren
                    sold_qty = min(trade['quantity'], running_position)
                    avg_cost_per_unit = total_cost / running_position if running_position > 0 else 0
                    total_cost -= sold_qty * avg_cost_per_unit
                    running_position -= sold_qty

        if running_position > 0 and total_cost > 0:
            return total_cost / running_position

        return None

    def _calculate_fifo_pnl(self, symbol: str) -> float:
        """Berechnet realisierten PnL mit FIFO-Methode"""
        if 'trades' not in st.session_state:
            return 0.0

        symbol_trades = [t for t in st.session_state['trades'] if t['symbol'] == symbol]

        # Vereinfachte FIFO-Simulation
        realized_pnl = 0.0
        open_longs = []  # [(price, quantity), ...]

        for trade in symbol_trades:
            if trade['action'] == 'BUY':
                open_longs.append((trade['price'], trade['quantity']))
            elif trade['action'] == 'SELL':
                remaining_sell_qty = trade['quantity']
                sell_price = trade['price']

                # FIFO: Älteste Käufe zuerst schließen
                while remaining_sell_qty > 0 and open_longs:
                    buy_price, buy_qty = open_longs[0]

                    # Vollständig oder teilweise schließen
                    close_qty = min(remaining_sell_qty, buy_qty)
                    realized_pnl += close_qty * (sell_price - buy_price)

                    # Position aktualisieren
                    remaining_sell_qty -= close_qty
                    if close_qty >= buy_qty:
                        open_longs.pop(0)
                    else:
                        open_longs[0] = (buy_price, buy_qty - close_qty)

        return realized_pnl

    def _update_portfolio_stats(self) -> None:
        """Aktualisiert Portfolio-Statistiken im Session State"""
        if 'portfolio_stats' not in st.session_state:
            st.session_state['portfolio_stats'] = {}

        # Hier könnte erweiterte Portfolio-Logik implementiert werden
        # Aktuell: Basis-Update Timestamp
        st.session_state['portfolio_stats']['last_update'] = datetime.now(self.timezone)

    def _empty_stats(self) -> Dict[str, Any]:
        """Gibt leere Trading-Statistiken zurück"""
        return {
            'total_trades': 0,
            'buy_trades': 0,
            'sell_trades': 0,
            'total_volume': 0,
            'buy_volume': 0,
            'sell_volume': 0,
            'realized_pnl': 0.0,
            'current_position': 0,
            'net_position': 0,
            'avg_trade_size': 0
        }