"""
RL Trading - Streamlit Hauptanwendung
Modularisierte Version der TradingView Lightweight Charts Trading App
Refactored mit Service Layer und Type Hints für bessere Architektur
"""

import streamlit as st
import time
import json
from typing import Dict, Any, Optional

from config.settings import PAGE_CONFIG, APP_CSS, init_session_state, DATA_CONFIG
from components.sidebar import render_sidebar
from components.trading_panel import render_trading_panel, render_debug_controls, render_debug_info
from services.data_service import DataService
from services.trading_service import TradingService
from services.chart_service import get_chart_service

# Streamlit Konfiguration
st.set_page_config(**PAGE_CONFIG)

def main() -> None:
    """Hauptfunktion der RL Trading App"""
    # CSS Styles laden
    st.markdown(APP_CSS, unsafe_allow_html=True)

    # Session State initialisieren
    init_session_state()

    # Auto-load Standard-Asset beim ersten Start
    _auto_load_default_asset()

    # App-Header
    st.title("🚀 RL Trading - Clean Lightweight Charts")
    st.subheader("Modularisierte Version mit erweiterbarer Architektur")

    # Sidebar rendern
    sidebar_results = render_sidebar()

    # Hauptinhalt
    col1, col2 = st.columns([3, 1])

    with col1:
        # Debug-Informationen anzeigen (falls aktiv)
        render_debug_info()

        # Chart-Bereich
        _render_chart_section(sidebar_results)

        # Debug-Steuerelemente (falls Debug-Modus aktiv)
        render_debug_controls()

    with col2:
        # Trading-Panel
        render_trading_panel(_get_current_data())

    # Auto-Refresh und Debug Auto-Play Logic
    _handle_auto_refresh_and_debug()

def _auto_load_default_asset() -> None:
    """Lädt automatisch das Standard-Asset beim ersten Start über DataService"""
    if st.session_state.live_data is None:
        data_service = DataService()
        data_service.auto_load_default_asset()

def _render_chart_section(sidebar_results: Dict[str, Any]) -> None:
    """
    Rendert den Chart-Bereich mit FastAPI Chart Server Integration

    Args:
        sidebar_results: Ergebnisse aus der Sidebar
    """
    st.subheader(f"📊 Chart: {st.session_state.selected_symbol}")

    chart_service = get_chart_service()

    # Prüfe Chart Server Status
    if not chart_service.is_server_running():
        st.error("❌ Chart Server nicht erreichbar. Starte `python chart_server.py` in einem separaten Terminal.")
        st.info("🚀 Server starten: `python chart_server.py`")
        return

    # Daten aktualisieren falls nötig über DataService
    if sidebar_results['refresh_clicked'] or sidebar_results['auto_refresh']:
        data_service = DataService()
        data_service.refresh_data()

    # Bestimme welche Daten verwendet werden sollen
    chart_data = _determine_chart_data()

    if chart_data:
        # Sende initiale Chart-Daten an FastAPI Server (nur bei Symbol/Interval Änderung)
        chart_rebuild_key = f"{st.session_state.selected_symbol}_{st.session_state.selected_interval}_{st.session_state.get('debug_start_date', 'live')}"

        if st.session_state.get('last_chart_key') != chart_rebuild_key:
            # Konvertiere Daten zu TradingView Format
            chart_data_tv = chart_service.convert_dataframe_to_chart_data(chart_data['data'])

            # Sende an Chart Server
            success = chart_service.set_chart_data(
                data=chart_data_tv,
                symbol=st.session_state.selected_symbol,
                interval=st.session_state.selected_interval
            )

            if success:
                st.success(f"📊 Chart initialisiert für {st.session_state.selected_symbol}")
                st.session_state.last_chart_key = chart_rebuild_key
            else:
                st.error("❌ Fehler beim Senden der Chart-Daten")

        # Handle Chart Updates (z.B. Debug Next Kerze)
        if st.session_state.get('chart_needs_update', False):
            chart_update_data = st.session_state.get('chart_update_data')

            if chart_update_data:
                # Sende Update an Chart Server
                success = chart_service.add_candle(chart_update_data)

                if success:
                    st.success("➡️ Chart-Update gesendet")
                else:
                    st.error("❌ Fehler beim Chart-Update")

            # Reset Update-Flags
            st.session_state.chart_needs_update = False
            st.session_state.chart_update_data = None

        # Zeige Chart Server Status
        status = chart_service.get_chart_status()
        if status:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🔗 Verbindungen", status['connections'])
            with col2:
                st.metric("📊 Kerzen", status['chart_state']['candles_count'])
            with col3:
                st.metric("📡 Symbol", status['chart_state']['symbol'])

        # Zeige FastAPI Chart in iframe
        chart_url = "http://localhost:8001"
        st.markdown(f"""
        <iframe src="{chart_url}"
                width="100%"
                height="500"
                frameborder="0"
                style="border: 1px solid #333; border-radius: 5px;">
        </iframe>
        """, unsafe_allow_html=True)

        # Markiere Chart als geladen
        st.session_state.chart_loaded = True
    else:
        st.info("Keine Daten verfügbar. Klicke auf 'Daten aktualisieren' in der Sidebar.")

def _refresh_data() -> None:
    """Aktualisiert die Marktdaten über DataService (Legacy - wird durch Service ersetzt)"""
    data_service = DataService()
    data_service.refresh_data()

def _determine_chart_data() -> Optional[Dict[str, Any]]:
    """
    Bestimmt welche Daten für den Chart verwendet werden sollen über DataService

    Returns:
        Chart-Daten (Live oder Debug gefiltert) oder None
    """
    data_service = DataService()
    return data_service.determine_chart_data()

def _get_current_data() -> Optional[Dict[str, Any]]:
    """
    Gibt die aktuellen Daten für das Trading-Panel zurück

    Returns:
        Aktuelle Marktdaten oder None
    """
    if st.session_state.debug_mode:
        return _determine_chart_data()
    else:
        return st.session_state.live_data

def _handle_auto_refresh_and_debug() -> None:
    """Behandelt Auto-Refresh und Debug Auto-Play Logic"""
    # Standard Auto-Refresh
    if st.session_state.auto_refresh and not st.session_state.debug_mode:
        time.sleep(2)
        st.rerun()

    # Debug Auto-Play Logic
    if st.session_state.debug_mode and st.session_state.debug_play_mode:
        _handle_debug_auto_play()

def _handle_debug_auto_play() -> None:
    """Behandelt Auto-Play Funktionalität im Debug-Modus mit FastAPI Integration"""
    # Berechne Delay basierend auf Geschwindigkeit
    delay = 2.0 / st.session_state.debug_speed  # Basis-Delay von 2 Sekunden bei 1x

    # Auto-advance zur nächsten Kerze
    if st.session_state.debug_all_data:
        from data.yahoo_finance import filter_debug_data
        from datetime import datetime, time as dt_time

        # Berechne maximalen Index basierend auf Startdatum
        debug_start_date = st.session_state.get('debug_start_date')
        if debug_start_date:
            start_datetime = datetime.combine(debug_start_date, dt_time.min)

            # Finde Startindex in den Originaldaten
            df = st.session_state.debug_all_data['data']

            # Timezone-Handling für korrekte Vergleiche
            from data.yahoo_finance import _make_timezone_compatible
            start_datetime = _make_timezone_compatible(start_datetime, df.index)

            start_index = None
            for i, timestamp in enumerate(df.index):
                if timestamp >= start_datetime:
                    start_index = i
                    break

            if start_index is not None:
                # Maximaler Index = Gesamtlänge - Startindex - 1
                max_debug_index = len(df) - start_index - 1

                if st.session_state.debug_current_index < max_debug_index:
                    # Kurzer Sleep für Auto-Play
                    time.sleep(delay)
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
                    chart_service.add_candle(chart_update_data)

                    st.rerun()
                else:
                    # Ende der Daten erreicht, stoppe Auto-Play
                    st.session_state.debug_play_mode = False
                    st.info("🏁 Ende der Debug-Daten erreicht. Auto-Play gestoppt.")
                    st.rerun()
            else:
                # Fallback: Original-Logik
                max_index = len(st.session_state.debug_all_data['data']) - 1
                if st.session_state.debug_current_index < max_index:
                    time.sleep(delay)
                    st.session_state.debug_current_index += 1

                    # Sende auch hier an FastAPI Chart Server
                    new_row = df.iloc[st.session_state.debug_current_index]
                    chart_update_data = {
                        'time': int(new_row.name.timestamp()),
                        'open': float(new_row['Open']),
                        'high': float(new_row['High']),
                        'low': float(new_row['Low']),
                        'close': float(new_row['Close'])
                    }

                    chart_service = get_chart_service()
                    chart_service.add_candle(chart_update_data)

                    st.rerun()
                else:
                    st.session_state.debug_play_mode = False
                    st.info("🏁 Ende der Debug-Daten erreicht. Auto-Play gestoppt.")
                    st.rerun()

# Error Handling und Logging
def handle_error(error: Exception, context: str = "Unbekannt") -> None:
    """
    Behandelt Fehler mit benutzerfreundlicher Anzeige

    Args:
        error: Der aufgetretene Fehler
        context: Kontext des Fehlers
    """
    error_msg = f"Fehler in {context}: {str(error)}"
    st.error(error_msg)

    # In Produktionsumgebung: Logging hinzufügen
    # logger.error(error_msg, exc_info=True)

# App-Informationen für Debugging
def show_debug_info() -> None:
    """Zeigt Debug-Informationen in der Sidebar"""
    if st.sidebar.checkbox("🔧 Debug Info anzeigen"):
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔧 Debug Informationen")
        st.sidebar.json({
            "Selected Symbol": st.session_state.selected_symbol,
            "Selected Interval": st.session_state.selected_interval,
            "Debug Mode": st.session_state.debug_mode,
            "Auto Refresh": st.session_state.auto_refresh,
            "Trades Count": len(st.session_state.trades),
            "Data Loaded": st.session_state.live_data is not None
        })

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        handle_error(e, "Hauptanwendung")
        st.error("Ein unerwarteter Fehler ist aufgetreten. Bitte lade die Seite neu.")