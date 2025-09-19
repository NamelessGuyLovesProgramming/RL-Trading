"""
App-weite Konfigurationsdatei
Zentrale Stelle für alle Einstellungen der RL Trading App
"""

import streamlit as st
from datetime import datetime, timedelta, date

# Page Configuration
PAGE_CONFIG = {
    "page_title": "RL Trading - Lightweight Charts Only",
    "page_icon": "🚀",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Default Values für Session State
DEFAULT_SESSION_STATE = {
    'selected_symbol': 'NQ=F',  # NASDAQ-100 Futures als Standard
    'selected_interval': '5m',
    'live_data': None,
    'last_update': None,
    'trades': [],
    'ai_trades': [],
    'human_trades': [],
    'trading_active': False,
    'auto_refresh': False,
    'chart_id': 0,  # For forcing chart refresh
    'show_volume': True,
    'show_ma20': True,
    'show_ma50': False,
    'show_bollinger': False,
    'show_rsi': False,
    'drawing_mode': None,  # 'line', 'rect', 'trendline', etc.
    'show_symbol_modal': False,  # Symbol selection modal state
    'symbol_search': '',  # Search term for symbol filtering
    'pending_symbol_change': None,  # Track pending symbol changes
    'symbol_changed_via_modal': False,  # Flag to prevent sidebar override
    # Debug Mode für historische Simulation
    'debug_mode': False,
    'debug_start_date': None,
    'debug_current_index': 0,
    'debug_play_mode': False,
    'debug_speed': 1.0,  # Geschwindigkeit (1x, 2x, 5x, 10x)
    'debug_show_panel': False,
    'debug_all_data': None,  # Alle verfügbaren historischen Daten
}

# Trading Intervals
INTERVAL_OPTIONS = ['1m', '5m', '15m', '1h', '1d']

# Standard Symbols für Quick Access
SYMBOL_OPTIONS = ['NQ=F', 'ES=F', 'YM=F', 'RTY=F', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'META']

# Debug Speed Options
DEBUG_SPEED_OPTIONS = [0.5, 1.0, 2.0, 5.0, 10.0]
DEBUG_SPEED_LABELS = ["0.5x", "1x", "2x", "5x", "10x"]

# Chart Configuration
CHART_CONFIG = {
    'width': 800,
    'height': 400,
    'layout': {
        'backgroundColor': '#000000',
        'textColor': '#d9d9d9'
    },
    'timeScale': {
        'timeVisible': True,
        'secondsVisible': False,
        'borderColor': '#485c7b'
    },
    'grid': {
        'vertLines': {'visible': False},
        'horzLines': {'visible': False}
    }
}

# Candlestick Series Configuration
CANDLESTICK_CONFIG = {
    'upColor': '#26a69a',
    'downColor': '#ef5350',
    'borderUpColor': '#26a69a',
    'borderDownColor': '#ef5350',
    'wickUpColor': '#26a69a',
    'wickDownColor': '#ef5350'
}

# Data Configuration
DATA_CONFIG = {
    'default_period': '5d',  # 5 Tage historische Daten
    'debug_period': '30d',   # 30 Tage für Debug-Modus
    'timezone': 'Europe/Berlin',  # UTC+2 Zeitzone
    'default_debug_date_offset': 30  # 30 Tage zurück für Debug-Start
}

# CSS Styles
APP_CSS = """
<style>
.stApp {
    background-color: #0E1111;
    color: #d1d4dc;
}
.data-panel {
    background-color: #1E2128;
    padding: 1rem;
    border-radius: 8px;
    margin: 0.5rem 0;
    border: 1px solid #2a2e39;
}
.metric-card {
    background-color: #2a2e39;
    padding: 0.8rem;
    border-radius: 6px;
    margin: 0.3rem;
    text-align: center;
}
.status-good { color: #26a69a; }
.status-bad { color: #ef5350; }
.status-neutral { color: #ffeb3b; }
.trade-button {
    width: 100%;
    margin: 0.2rem 0;
}
.symbol-item {
    background: #2a2e39;
    color: #d1d4dc;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid transparent;
}
.symbol-item:hover {
    background: #26a69a;
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(38, 166, 154, 0.3);
}
</style>
"""

def get_default_debug_date():
    """Gibt das Standard-Startdatum für Debug-Modus zurück (30 Tage zurück)"""
    return date.today() - timedelta(days=DATA_CONFIG['default_debug_date_offset'])

def init_session_state():
    """Initialisiert den Session State mit Standard-Werten"""
    for key, value in DEFAULT_SESSION_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value