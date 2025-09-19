"""
Trading Panel Komponente - UI Layer
Enthält nur UI-Darstellung, Business Logic wurde zu Services verschoben
Refactored für bessere Separation of Concerns
"""

import streamlit as st
from datetime import datetime
from typing import Dict, Any, Optional

from config.settings import DEBUG_SPEED_OPTIONS, DEBUG_SPEED_LABELS
from services.trading_service import TradingService
from services.data_service import DataService
from services.chart_service import get_chart_service

def render_trading_panel(data_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Rendert das Trading-Panel in der rechten Spalte
    Nur UI-Rendering, Business Logic in TradingService

    Args:
        data_dict: Aktuelle Marktdaten

    Returns:
        Trading-Panel Ergebnisse
    """
    st.subheader("💼 Trading")

    if not data_dict:
        st.info("Keine Daten verfügbar")
        return {}

    # Aktueller Preis über DataService
    data_service = DataService()
    current_price = data_service.get_latest_price(data_dict) or 0.0
    st.metric("Aktueller Preis", f"${current_price:.2f}")

    # Position Management Panel
    position_results = _render_position_panel(current_price)

    # Trading Buttons (Original BUY/SELL)
    trade_results = _render_trading_buttons(current_price)

    # Aktive Positionen anzeigen
    _display_active_positions()

    # Trades anzeigen
    _display_trades()

    # Trade-Statistiken
    _display_trade_statistics()

    # SL/TP Monitoring
    _monitor_stop_loss_take_profit(current_price)

    # Merge results
    trade_results.update(position_results)
    return trade_results

def _render_trading_buttons(current_price: float) -> Dict[str, Any]:
    """
    Rendert BUY/SELL Buttons - UI Only
    Trading Logic delegiert an TradingService

    Args:
        current_price: Aktueller Marktpreis

    Returns:
        Button-Ergebnisse
    """
    col_buy, col_sell = st.columns(2)

    buy_clicked = False
    sell_clicked = False

    trading_service = TradingService()

    with col_buy:
        if st.button("🟢 BUY", key="buy_btn", use_container_width=True):
            buy_clicked = True
            success = trading_service.add_trade('BUY', current_price, 'Human')
            if success:
                st.success(f"BUY @ ${current_price:.2f}")

    with col_sell:
        if st.button("🔴 SELL", key="sell_btn", use_container_width=True):
            sell_clicked = True
            success = trading_service.add_trade('SELL', current_price, 'Human')
            if success:
                st.success(f"SELL @ ${current_price:.2f}")

    return {
        'buy_clicked': buy_clicked,
        'sell_clicked': sell_clicked,
        'price': current_price
    }

def add_trade(trade_type: str, price: float, source: str = 'Human') -> bool:
    """
    Legacy-Funktion - Ersetzt durch TradingService.add_trade()
    Wird beibehalten für Backwards Compatibility

    Args:
        trade_type: 'BUY' oder 'SELL'
        price: Ausführungspreis
        source: 'Human' oder 'AI'

    Returns:
        True wenn erfolgreich
    """
    trading_service = TradingService()
    return trading_service.add_trade(trade_type, price, source)

def _display_trades() -> None:
    """Zeigt die letzten Trades an - UI Only"""
    if not st.session_state.trades:
        return

    st.subheader("🔄 Aktuelle Trades")

    # Die letzten 10 Trades anzeigen
    recent_trades = st.session_state.trades[-10:]

    for trade in reversed(recent_trades):
        timestamp = trade['timestamp'].strftime("%H:%M:%S")
        color = "🟢" if trade['type'] == 'BUY' else "🔴"
        source_icon = "👤" if trade['source'] == 'Human' else "🤖"
        symbol = trade.get('symbol', 'N/A')

        st.write(f"{timestamp} {color} {source_icon} {trade['type']} {symbol} @ ${trade['price']:.2f}")

def _display_trade_statistics() -> None:
    """Zeigt Trade-Statistiken an - UI Only"""
    # Statistiken über TradingService laden
    trading_service = TradingService()
    stats = trading_service.get_trading_statistics()
    if not stats:
        return

    st.subheader("📈 Statistiken")

    # Basis-Statistiken
    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total Trades", stats['total_trades'])
        st.metric("Buy Trades", stats['buy_trades'])

    with col2:
        st.metric("Sell Trades", stats['sell_trades'])
        st.metric("Current Position", stats['current_position'])

    # Erweiterte Statistiken (falls verfügbar)
    if stats['total_trades'] > 0:
        _display_advanced_statistics(stats)

def get_trade_stats() -> Optional[Dict[str, Any]]:
    """
    Legacy-Funktion - Ersetzt durch TradingService.get_trading_statistics()
    Wird beibehalten für Backwards Compatibility

    Returns:
        Statistiken oder None
    """
    if not st.session_state.trades:
        return None

    trades = st.session_state.trades
    total_trades = len(trades)
    human_trades = len(st.session_state.human_trades)
    ai_trades = len(st.session_state.ai_trades)

    # TODO: Erweiterte P&L Berechnung
    success_rate = 0.0

    return {
        'total': total_trades,
        'human': human_trades,
        'ai': ai_trades,
        'success_rate': success_rate,
        'trades_today': _count_trades_today(),
        'avg_price': _calculate_avg_price()
    }

def _count_trades_today():
    """Zählt Trades von heute"""
    today = datetime.now().date()
    return sum(1 for trade in st.session_state.trades
               if trade['timestamp'].date() == today)

def _calculate_avg_price():
    """Berechnet Durchschnittspreis aller Trades"""
    if not st.session_state.trades:
        return 0.0

    prices = [trade['price'] for trade in st.session_state.trades]
    return sum(prices) / len(prices)

def _display_advanced_statistics(stats):
    """
    Zeigt erweiterte Statistiken an

    Args:
        stats (dict): Basis-Statistiken
    """
    st.markdown("---")
    st.markdown("**Erweiterte Statistiken**")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Trades heute", stats['trades_today'])

    with col2:
        st.metric("Ø Preis", f"${stats['avg_price']:.2f}")

def render_debug_controls():
    """
    Rendert Debug-Steuerelemente im Hauptbereich

    Returns:
        dict: Debug-Kontroll-Ergebnisse
    """
    if not st.session_state.debug_mode:
        return {}

    st.markdown("### 🎮 Debug Controls")

    debug_col1, debug_col2, debug_col3, debug_col4 = st.columns([2, 2, 2, 2])

    results = {}

    with debug_col1:
        # Next Button
        if st.button("➡️ Next Kerze", key="debug_next", use_container_width=True):
            results['next_clicked'] = True
            if st.session_state.debug_all_data and st.session_state.debug_start_date:
                from datetime import datetime, time as dt_time

                # Berechne maximalen Index basierend auf Startdatum
                start_datetime = datetime.combine(st.session_state.debug_start_date, dt_time.min)
                df = st.session_state.debug_all_data['data']

                # Timezone-Handling für korrekte Vergleiche
                from data.yahoo_finance import _make_timezone_compatible
                start_datetime = _make_timezone_compatible(start_datetime, df.index)

                # Finde Startindex
                start_index = None
                for i, timestamp in enumerate(df.index):
                    if timestamp >= start_datetime:
                        start_index = i
                        break

                if start_index is not None:
                    # Maximaler Debug-Index = Gesamtlänge - Startindex - 1
                    max_debug_index = len(df) - start_index - 1

                    if st.session_state.debug_current_index < max_debug_index:
                        # Erhöhe Index
                        st.session_state.debug_current_index += 1

                        # Berechne neue Kerzen-Daten für FastAPI Chart-Update
                        new_absolute_index = start_index + st.session_state.debug_current_index
                        new_row = df.iloc[new_absolute_index]

                        # Erstelle Chart-Update-Daten
                        chart_update_data = {
                            'time': int(new_row.name.timestamp()),
                            'open': float(new_row['Open']),
                            'high': float(new_row['High']),
                            'low': float(new_row['Low']),
                            'close': float(new_row['Close'])
                        }

                        # Sende direkt an FastAPI Chart Server
                        chart_service = get_chart_service()
                        success = chart_service.add_candle(chart_update_data)

                        if success:
                            st.success("➡️ Kerze hinzugefügt")
                        else:
                            st.error("❌ Fehler beim Chart-Update")

                        # Kein st.rerun() mehr - Chart wird über WebSocket aktualisiert

    with debug_col2:
        # Play/Pause Button
        play_text = "⏸️ Pause" if st.session_state.debug_play_mode else "▶️ Play"
        if st.button(play_text, key="debug_play", use_container_width=True):
            results['play_pause_clicked'] = True
            st.session_state.debug_play_mode = not st.session_state.debug_play_mode
            st.rerun()

    with debug_col3:
        # Speed Control
        current_speed_index = 1  # Default 1x
        if st.session_state.debug_speed in DEBUG_SPEED_OPTIONS:
            current_speed_index = DEBUG_SPEED_OPTIONS.index(st.session_state.debug_speed)

        new_speed_index = st.selectbox(
            "Speed",
            range(len(DEBUG_SPEED_OPTIONS)),
            index=current_speed_index,
            format_func=lambda x: DEBUG_SPEED_LABELS[x],
            key="debug_speed_select"
        )
        st.session_state.debug_speed = DEBUG_SPEED_OPTIONS[new_speed_index]

    with debug_col4:
        # Progress info
        if st.session_state.debug_all_data:
            total_candles = len(st.session_state.debug_all_data['data'])
            current_candle = st.session_state.debug_current_index + 1
            progress = current_candle / total_candles
            st.metric("Progress", f"{progress:.1%}")

    return results

def render_debug_info():
    """
    Rendert Debug-Informationen im Hauptbereich

    Returns:
        dict: Debug-Info
    """
    if not st.session_state.debug_mode:
        return {}

    # Debug Mode Indicator mit korrekter Datum-Berechnung
    debug_current_index = st.session_state.get('debug_current_index', 0)
    debug_start_date = st.session_state.get('debug_start_date')
    debug_all_data = st.session_state.get('debug_all_data')

    debug_info = f"🐛 Debug-Modus | Iteration {debug_current_index + 1}"

    if debug_all_data and debug_start_date:
        from datetime import datetime, time as dt_time

        # Berechne den aktuellen absoluten Index basierend auf Startdatum
        start_datetime = datetime.combine(debug_start_date, dt_time.min)
        df = debug_all_data['data']

        # Timezone-Handling für korrekte Vergleiche
        from data.yahoo_finance import _make_timezone_compatible
        start_datetime = _make_timezone_compatible(start_datetime, df.index)

        # Finde Startindex in den Originaldaten
        start_index = None
        for i, timestamp in enumerate(df.index):
            if timestamp >= start_datetime:
                start_index = i
                break

        if start_index is not None:
            # Absoluter Index = Startindex + aktueller Debug-Index
            absolute_index = start_index + debug_current_index

            if absolute_index < len(df):
                # Zeige das Datum der aktuellen Kerze
                current_timestamp = df.index[absolute_index]
                current_date = current_timestamp.strftime("%Y-%m-%d %H:%M")
                debug_info += f" | {current_date}"

                # Zeige verbleibende Kerzen bis heute
                remaining_candles = len(df) - absolute_index - 1
                debug_info += f" | {remaining_candles} verbleibend"
            else:
                debug_info += " | Ende erreicht"
        else:
            debug_info += " | Startdatum nicht gefunden"

    st.info(debug_info)

    return {
        'current_index': debug_current_index,
        'total_candles': len(debug_all_data['data']) if debug_all_data else 0,
        'current_date': current_date if 'current_date' in locals() else None
    }

def _render_position_panel(current_price: float) -> Dict[str, Any]:
    """
    Rendert Position Management Panel mit Long/Short und SL/TP

    Args:
        current_price: Aktueller Marktpreis

    Returns:
        Position Panel Ergebnisse
    """
    st.subheader("🎯 Position Management")

    trading_service = TradingService()
    results = {}

    # Input-Felder für Position Management
    col1, col2 = st.columns(2)

    with col1:
        quantity = st.number_input("Quantität", min_value=1, max_value=100, value=1, key="pos_quantity")

    with col2:
        risk_pct = st.slider("Risk %", min_value=0.5, max_value=5.0, value=1.0, step=0.1, key="risk_pct")

    # SL/TP Berechnung basierend auf Risk %
    risk_amount = current_price * (risk_pct / 100)

    # Long Position Panel
    st.markdown("### 🟢 Long Position")
    col_long1, col_long2, col_long3 = st.columns(3)

    with col_long1:
        if st.button("🟢 LONG", key="long_btn", use_container_width=True):
            # Berechne SL/TP für Long
            stop_loss = current_price - risk_amount
            take_profit = current_price + (risk_amount * 2)  # 2:1 R/R

            success = trading_service.open_long_position(
                entry_price=current_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            if success:
                results['long_opened'] = True

    with col_long2:
        st.metric("SL", f"${(current_price - risk_amount):.2f}", delta=f"-{risk_pct}%")

    with col_long3:
        st.metric("TP", f"${(current_price + risk_amount * 2):.2f}", delta=f"+{risk_pct * 2}%")

    # Short Position Panel
    st.markdown("### 🔴 Short Position")
    col_short1, col_short2, col_short3 = st.columns(3)

    with col_short1:
        if st.button("🔴 SHORT", key="short_btn", use_container_width=True):
            # Berechne SL/TP für Short
            stop_loss = current_price + risk_amount
            take_profit = current_price - (risk_amount * 2)  # 2:1 R/R

            success = trading_service.open_short_position(
                entry_price=current_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            if success:
                results['short_opened'] = True

    with col_short2:
        st.metric("SL", f"${(current_price + risk_amount):.2f}", delta=f"+{risk_pct}%")

    with col_short3:
        st.metric("TP", f"${(current_price - risk_amount * 2):.2f}", delta=f"-{risk_pct * 2}%")

    return results

def _display_active_positions() -> None:
    """Zeigt aktive Positionen mit SL/TP an"""
    trading_service = TradingService()
    active_positions = trading_service.get_active_positions()

    if not active_positions:
        return

    st.subheader("📊 Aktive Positionen")

    for position in active_positions:
        with st.expander(f"{position['type']} {position['id']} - {position['symbol']}"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Entry", f"${position['entry_price']:.2f}")
                st.metric("Quantity", position['quantity'])

            with col2:
                if position['stop_loss']:
                    st.metric("🛡️ Stop Loss", f"${position['stop_loss']:.2f}")
                else:
                    st.write("🛡️ Stop Loss: -")

                if position['take_profit']:
                    st.metric("🎯 Take Profit", f"${position['take_profit']:.2f}")
                else:
                    st.write("🎯 Take Profit: -")

            with col3:
                # Position Status
                timestamp = position['timestamp'].strftime("%H:%M:%S")
                st.write(f"⏰ Opened: {timestamp}")

                # Manual Close Button
                if st.button(f"❌ Close {position['id']}", key=f"close_{position['id']}"):
                    data_service = DataService()
                    current_price = data_service.get_latest_price(st.session_state.live_data) or 0.0
                    trading_service.close_position_by_id(position['id'], current_price)
                    st.rerun()

def _monitor_stop_loss_take_profit(current_price: float) -> None:
    """Überwacht SL/TP Trigger automatisch"""
    if current_price <= 0:
        return

    trading_service = TradingService()
    executed_orders = trading_service.check_stop_loss_take_profit(current_price)

    # Zeige ausgeführte Orders
    for order in executed_orders:
        st.success(order)

    # Auto-Refresh bei ausgeführten Orders
    if executed_orders:
        st.rerun()