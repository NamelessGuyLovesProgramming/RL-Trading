"""
Sidebar-Komponente für RL Trading App
Enthält alle Sidebar-Elemente: Symbol-Auswahl, Einstellungen, Debug-Panel
"""

import streamlit as st
from datetime import date, timedelta
from config.settings import SYMBOL_OPTIONS, INTERVAL_OPTIONS, DEBUG_SPEED_OPTIONS, DEBUG_SPEED_LABELS, get_default_debug_date
from data.yahoo_finance import get_yfinance_data, get_debug_data

def render_sidebar():
    """
    Rendert die komplette Sidebar mit allen Steuerelementen

    Returns:
        dict: Dictionary mit allen Sidebar-Werten
    """
    st.sidebar.title("⚙️ Einstellungen")

    # Symbol Selection
    symbol_selection = _render_symbol_selection()

    # Interval Selection
    interval_selection = _render_interval_selection()

    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-Refresh", value=st.session_state.auto_refresh)
    st.session_state.auto_refresh = auto_refresh

    # Debug Panel
    debug_panel_results = _render_debug_panel()

    # Data Refresh Button
    refresh_clicked = st.sidebar.button("🔄 Daten aktualisieren")

    return {
        'symbol': symbol_selection,
        'interval': interval_selection,
        'auto_refresh': auto_refresh,
        'refresh_clicked': refresh_clicked,
        'debug_results': debug_panel_results
    }

def _render_symbol_selection():
    """
    Rendert die Symbol-Auswahl

    Returns:
        str: Gewähltes Symbol
    """
    current_index = 0
    if st.session_state.selected_symbol in SYMBOL_OPTIONS:
        current_index = SYMBOL_OPTIONS.index(st.session_state.selected_symbol)

    selected_symbol = st.sidebar.selectbox(
        "Symbol",
        options=SYMBOL_OPTIONS,
        index=current_index,
        help="Wähle ein Trading-Symbol"
    )

    st.session_state.selected_symbol = selected_symbol
    return selected_symbol

def _render_interval_selection():
    """
    Rendert die Intervall-Auswahl

    Returns:
        str: Gewähltes Intervall
    """
    current_index = 0
    if st.session_state.selected_interval in INTERVAL_OPTIONS:
        current_index = INTERVAL_OPTIONS.index(st.session_state.selected_interval)

    selected_interval = st.sidebar.selectbox(
        "Intervall",
        options=INTERVAL_OPTIONS,
        index=current_index,
        help="Wähle ein Chart-Intervall"
    )

    st.session_state.selected_interval = selected_interval
    return selected_interval

def _render_debug_panel():
    """
    Rendert das Debug-Panel für historische Simulation

    Returns:
        dict: Debug-Panel Ergebnisse
    """
    st.sidebar.markdown("---")

    # Debug Panel Toggle
    if st.sidebar.button("🐛 Debug Modus"):
        st.session_state.debug_show_panel = not st.session_state.debug_show_panel

    debug_results = {'started': False, 'stopped': False}

    if st.session_state.debug_show_panel:
        st.sidebar.markdown("### 🔍 Debug Panel")

        # Debug Start Date
        default_date = get_default_debug_date()
        debug_date = st.sidebar.date_input(
            "Start-Datum für Debug",
            value=default_date,
            key="debug_date_picker",
            help="Wähle das Startdatum für die historische Simulation"
        )

        # Debug Setup Button
        if st.sidebar.button("▶️ Debug Starten", help="Startet den Debug-Modus mit historischen Daten"):
            debug_results['started'] = True
            debug_results['start_date'] = debug_date

            # Session State für Debug-Modus setzen
            st.session_state.debug_mode = True
            st.session_state.debug_start_date = debug_date
            st.session_state.debug_current_index = 0
            st.session_state.debug_play_mode = False
            st.session_state.debug_show_panel = False

            # Lade erweiterte historische Daten für Debug
            with st.spinner("Lade Debug-Daten..."):
                st.session_state.debug_all_data = get_debug_data(
                    st.session_state.selected_symbol,
                    st.session_state.selected_interval
                )

            st.rerun()

        # Debug beenden (nur anzeigen wenn Debug aktiv)
        if st.session_state.debug_mode and st.sidebar.button("🛑 Debug Beenden", help="Beendet den Debug-Modus"):
            debug_results['stopped'] = True

            # Debug-Modus zurücksetzen
            st.session_state.debug_mode = False
            st.session_state.debug_show_panel = False
            st.session_state.debug_all_data = None

            st.rerun()

        # Debug Info anzeigen
        if st.session_state.debug_mode:
            st.sidebar.info(f"🐛 Debug aktiv seit {st.session_state.debug_start_date}")

    return debug_results

def render_trading_controls():
    """
    Rendert Trading-Kontrollelemente in der Sidebar

    Returns:
        dict: Trading-Kontroll-Ergebnisse
    """
    if not st.session_state.get('trading_section_enabled', False):
        return {}

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💼 Trading")

    # Trading aktivieren/deaktivieren
    trading_active = st.sidebar.checkbox(
        "Trading aktiviert",
        value=st.session_state.trading_active,
        help="Aktiviert/deaktiviert Trading-Funktionen"
    )
    st.session_state.trading_active = trading_active

    # AI Trading Settings (falls aktiviert)
    ai_trading = st.sidebar.checkbox(
        "AI Trading",
        value=st.session_state.get('ai_trading_enabled', False),
        help="Aktiviert automatisches AI Trading"
    )

    return {
        'trading_active': trading_active,
        'ai_trading': ai_trading
    }

def render_chart_settings():
    """
    Rendert Chart-Einstellungen in der Sidebar

    Returns:
        dict: Chart-Einstellungen
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Chart-Einstellungen")

    # Indikatoren
    show_volume = st.sidebar.checkbox("Volume", value=st.session_state.show_volume)
    show_ma20 = st.sidebar.checkbox("MA 20", value=st.session_state.show_ma20)
    show_ma50 = st.sidebar.checkbox("MA 50", value=st.session_state.show_ma50)
    show_bollinger = st.sidebar.checkbox("Bollinger Bands", value=st.session_state.show_bollinger)

    # Session State aktualisieren
    st.session_state.show_volume = show_volume
    st.session_state.show_ma20 = show_ma20
    st.session_state.show_ma50 = show_ma50
    st.session_state.show_bollinger = show_bollinger

    return {
        'show_volume': show_volume,
        'show_ma20': show_ma20,
        'show_ma50': show_ma50,
        'show_bollinger': show_bollinger
    }

def render_debug_status():
    """
    Rendert Debug-Status Informationen

    Returns:
        dict: Debug-Status
    """
    if not st.session_state.debug_mode:
        return {}

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🐛 Debug Status")

    # Aktueller Debug-Fortschritt
    if st.session_state.debug_all_data:
        total_candles = len(st.session_state.debug_all_data['data'])
        current_candle = st.session_state.debug_current_index + 1
        progress = current_candle / total_candles

        st.sidebar.progress(progress)
        st.sidebar.caption(f"Kerze {current_candle} von {total_candles}")

        # Debug-Geschwindigkeit
        current_speed = st.session_state.debug_speed
        speed_label = DEBUG_SPEED_LABELS[DEBUG_SPEED_OPTIONS.index(current_speed)]
        st.sidebar.caption(f"Geschwindigkeit: {speed_label}")

        # Play/Pause Status
        status = "▶️ Läuft" if st.session_state.debug_play_mode else "⏸️ Pausiert"
        st.sidebar.caption(f"Status: {status}")

    return {
        'progress': progress if 'progress' in locals() else 0,
        'current_candle': current_candle if 'current_candle' in locals() else 0,
        'total_candles': total_candles if 'total_candles' in locals() else 0
    }