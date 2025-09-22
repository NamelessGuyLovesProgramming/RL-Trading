"""
Pure TradingView Lightweight Charts Trading App
Nur Lightweight Charts - Kein TradingView Widget
Mit Trading Features und AI Integration
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime, timedelta
import time

st.set_page_config(
    page_title="RL Trading - Lightweight Charts Only",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS
st.markdown("""
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
""", unsafe_allow_html=True)

# Session State
def init_session_state():
    defaults = {
        'selected_symbol': 'NQ=F',
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

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# Available Assets Configuration
AVAILABLE_ASSETS = {
    "stocks": [
        {"symbol": "AAPL", "name": "Apple Inc.", "description": "Technology - Consumer Electronics"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "description": "Technology - Software"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "description": "Technology - Internet Services"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "description": "Automotive - Electric Vehicles"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "description": "Consumer Discretionary - E-commerce"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "description": "Technology - Semiconductors"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "description": "Technology - Social Media"},
        {"symbol": "NFLX", "name": "Netflix Inc.", "description": "Entertainment - Streaming"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "description": "Technology - Semiconductors"},
        {"symbol": "CRM", "name": "Salesforce Inc.", "description": "Technology - Cloud Software"},
        {"symbol": "INTC", "name": "Intel Corporation", "description": "Technology - Semiconductors"},
        {"symbol": "BABA", "name": "Alibaba Group", "description": "Technology - E-commerce China"},
        {"symbol": "PYPL", "name": "PayPal Holdings", "description": "Financial - Digital Payments"},
        {"symbol": "DIS", "name": "The Walt Disney Company", "description": "Entertainment - Media"},
        {"symbol": "V", "name": "Visa Inc.", "description": "Financial - Payment Networks"},
        {"symbol": "MA", "name": "Mastercard Inc.", "description": "Financial - Payment Networks"}
    ],
    "crypto": [
        {"symbol": "BTC-USD", "name": "Bitcoin", "description": "Cryptocurrency - Digital Gold"},
        {"symbol": "ETH-USD", "name": "Ethereum", "description": "Cryptocurrency - Smart Contracts"},
        {"symbol": "ADA-USD", "name": "Cardano", "description": "Cryptocurrency - Proof of Stake"},
        {"symbol": "DOT-USD", "name": "Polkadot", "description": "Cryptocurrency - Interoperability"},
        {"symbol": "LINK-USD", "name": "Chainlink", "description": "Cryptocurrency - Oracle Network"},
        {"symbol": "LTC-USD", "name": "Litecoin", "description": "Cryptocurrency - Digital Silver"}
    ],
    "forex": [
        {"symbol": "EURUSD=X", "name": "EUR/USD", "description": "Euro vs US Dollar"},
        {"symbol": "GBPUSD=X", "name": "GBP/USD", "description": "British Pound vs US Dollar"},
        {"symbol": "USDJPY=X", "name": "USD/JPY", "description": "US Dollar vs Japanese Yen"},
        {"symbol": "USDCHF=X", "name": "USD/CHF", "description": "US Dollar vs Swiss Franc"}
    ],
    "indices": [
        {"symbol": "^GSPC", "name": "S&P 500", "description": "US Large Cap Index"},
        {"symbol": "^IXIC", "name": "NASDAQ Composite", "description": "US Tech Index"},
        {"symbol": "^DJI", "name": "Dow Jones Industrial", "description": "US Blue Chip Index"},
        {"symbol": "^RUT", "name": "Russell 2000", "description": "US Small Cap Index"}
    ]
}

def validate_symbol(symbol):
    """Check if symbol is in available assets"""
    for category in AVAILABLE_ASSETS.values():
        for asset in category:
            if asset["symbol"] == symbol:
                return True
    return False

def get_asset_info(symbol):
    """Get asset information from available assets"""
    for category in AVAILABLE_ASSETS.values():
        for asset in category:
            if asset["symbol"] == symbol:
                return asset
    return None

def get_yfinance_data(symbol, period="1d", interval="5m"):
    """Hole Live-Daten von Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return None

        # Timezone handling für TradingView - UTC+2 (Europa/Berlin)
        if hist.index.tz is not None:
            hist.index = hist.index.tz_convert('Europe/Berlin').tz_localize(None)
        else:
            # Falls keine Zeitzone gesetzt ist, füge UTC+2 hinzu
            import pytz
            berlin_tz = pytz.timezone('Europe/Berlin')
            hist.index = hist.index.tz_localize('UTC').tz_convert(berlin_tz).tz_localize(None)

        hist = hist.round(2)
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
        st.error(f"Fehler beim Laden: {e}")
        return None

def filter_debug_data(data_dict, debug_start_date, current_index):
    """Filter data for debug mode up to current index"""
    if not data_dict or data_dict['data'].empty:
        return None

    df = data_dict['data'].copy()

    # Convert debug_start_date to datetime if it's a date
    if hasattr(debug_start_date, 'date'):
        start_datetime = debug_start_date
    else:
        from datetime import datetime
        start_datetime = datetime.combine(debug_start_date, datetime.min.time())

    # Filter data from start_date onwards
    df_filtered = df[df.index >= start_datetime]

    # Take only up to current_index candles
    if current_index < len(df_filtered):
        df_filtered = df_filtered.iloc[:current_index + 1]

    # Create new data_dict with filtered data
    return {
        'data': df_filtered,
        'current_price': df_filtered['Close'].iloc[-1] if not df_filtered.empty else 0,
        'symbol': data_dict['symbol'],
        'last_update': data_dict['last_update'],
        'info': data_dict['info']
    }

def create_trading_chart(data_dict, trades=None, show_volume=True, show_ma20=True, show_ma50=False, show_bollinger=False, selected_symbol="AAPL", selected_interval="1h"):
    """Create minimal working chart"""
    if not data_dict or data_dict['data'].empty:
        return "<div>Keine Daten verfügbar</div>"

    df = data_dict['data']
    chart_data = []

    for idx, row in df.iterrows():
        chart_data.append({
            'time': int(idx.timestamp()),
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close'])
        })

    chart_id = f'chart_{int(time.time() * 1000)}'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Minimal Chart Test</title>
    </head>
    <body>
        <div id="{chart_id}" style="width: 800px; height: 400px; background: #000;"></div>

        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>

        <script>
            console.log('🚀 SIMPLE CHART: Starting...');

            // Wait for library
            setTimeout(() => {{
                console.log('📊 SIMPLE CHART: Creating chart...');

                const chart = LightweightCharts.createChart(document.getElementById('{chart_id}'), {{
                    width: 800,
                    height: 400,
                    layout: {{
                        backgroundColor: '#000000',
                        textColor: '#d9d9d9'
                    }},
                    timeScale: {{
                        timeVisible: true,
                        secondsVisible: false,
                        borderColor: '#485c7b'
                    }},
                    grid: {{
                        vertLines: {{
                            visible: false
                        }},
                        horzLines: {{
                            visible: false
                        }}
                    }}
                }});

                console.log('✅ SIMPLE CHART: Chart created');

                const candlestickSeries = chart.addCandlestickSeries({{
                    upColor: '#26a69a',
                    downColor: '#ef5350',
                    borderUpColor: '#26a69a',
                    borderDownColor: '#ef5350',
                    wickUpColor: '#26a69a',
                    wickDownColor: '#ef5350'
                }});

                console.log('✅ SIMPLE CHART: Series added');

                const data = {json.dumps(chart_data)};
                console.log('📊 SIMPLE CHART: Data:', data.length, 'points');

                candlestickSeries.setData(data);
                console.log('✅ SIMPLE CHART: Data set - you should see candles!');

                chart.timeScale().fitContent();

            }}, 1000);
        </script>
    </body>
    </html>
    """

    return html

def add_trade(trade_type, price, source='Human'):
    """Add trade to session state"""
    if st.session_state.live_data:
        current_time = st.session_state.live_data['last_update']

        trade = {
            'timestamp': current_time,
            'type': trade_type,
            'price': price,
            'source': source
        }

        st.session_state.trades.append(trade)

        if source == 'Human':
            st.session_state.human_trades.append(trade)
        else:
            st.session_state.ai_trades.append(trade)

def display_trades():
    """Display recent trades"""
    if st.session_state.trades:
        st.subheader("🔄 Aktuelle Trades")

        recent_trades = st.session_state.trades[-10:]  # Last 10 trades

        for trade in reversed(recent_trades):
            timestamp = trade['timestamp'].strftime("%H:%M:%S")
            color = "🟢" if trade['type'] == 'BUY' else "🔴"
            source_icon = "👤" if trade['source'] == 'Human' else "🤖"

            st.write(f"{timestamp} {color} {source_icon} {trade['type']} @ ${trade['price']:.2f}")

def get_trade_stats():
    """Calculate trade statistics"""
    if not st.session_state.trades:
        return None

    trades = st.session_state.trades
    total_trades = len(trades)
    human_trades = len(st.session_state.human_trades)
    ai_trades = len(st.session_state.ai_trades)

    return {
        'total': total_trades,
        'human': human_trades,
        'ai': ai_trades,
        'success_rate': 0  # TODO: Calculate based on P&L
    }

# Main App
def main():
    init_session_state()

    # Auto-load default asset on startup if no data exists
    if st.session_state.live_data is None:
        with st.spinner("Lade Standard-Asset (NQ=F)..."):
            st.session_state.live_data = get_yfinance_data(
                st.session_state.selected_symbol,
                period="5d",
                interval=st.session_state.selected_interval
            )

    st.title("🚀 RL Trading - Clean Lightweight Charts")
    st.subheader("Simplified Working Version")

    # Sidebar
    st.sidebar.title("⚙️ Einstellungen")

    # Symbol Selection
    symbol_options = ['NQ=F', 'ES=F', 'YM=F', 'RTY=F', 'AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'META']
    st.session_state.selected_symbol = st.sidebar.selectbox(
        "Symbol",
        options=symbol_options,
        index=symbol_options.index(st.session_state.selected_symbol)
    )

    # Interval Selection
    interval_options = ['1m', '5m', '15m', '1h', '1d']
    st.session_state.selected_interval = st.sidebar.selectbox(
        "Interval",
        options=interval_options,
        index=interval_options.index(st.session_state.selected_interval)
    )

    # Auto-refresh toggle
    st.session_state.auto_refresh = st.sidebar.checkbox("Auto-Refresh", value=st.session_state.auto_refresh)

    # Debug Panel
    st.sidebar.markdown("---")
    if st.sidebar.button("🐛 Debug Modus"):
        st.session_state.debug_show_panel = not st.session_state.debug_show_panel

    if st.session_state.debug_show_panel:
        st.sidebar.markdown("### 🔍 Debug Panel")

        # Debug Start Date
        from datetime import date, timedelta
        default_date = date.today() - timedelta(days=30)
        debug_date = st.sidebar.date_input(
            "Start-Datum für Debug",
            value=default_date,
            key="debug_date_picker"
        )

        # Debug Setup Button
        if st.sidebar.button("▶️ Debug Starten"):
            st.session_state.debug_mode = True
            st.session_state.debug_start_date = debug_date
            st.session_state.debug_current_index = 0
            st.session_state.debug_play_mode = False
            st.session_state.debug_show_panel = False

            # Lade mehr historische Daten für Debug
            with st.spinner("Lade Debug-Daten..."):
                st.session_state.debug_all_data = get_yfinance_data(
                    st.session_state.selected_symbol,
                    period="30d",  # 30 Tage für mehr Debug-Daten
                    interval=st.session_state.selected_interval
                )
            st.rerun()

        # Debug beenden
        if st.session_state.debug_mode and st.sidebar.button("🛑 Debug Beenden"):
            st.session_state.debug_mode = False
            st.session_state.debug_show_panel = False
            st.rerun()

    if st.sidebar.button("🔄 Daten aktualisieren") or st.session_state.auto_refresh:
        with st.spinner("Lade Daten..."):
            st.session_state.live_data = get_yfinance_data(
                st.session_state.selected_symbol,
                period="5d",
                interval=st.session_state.selected_interval
            )

    # Main content
    col1, col2 = st.columns([3, 1])

    with col1:
        # Debug Mode Indicator
        if st.session_state.debug_mode:
            debug_info = f"🐛 Debug-Modus | Kerze {st.session_state.debug_current_index + 1}"
            if st.session_state.debug_all_data:
                total_candles = len(st.session_state.debug_all_data['data'])
                debug_info += f" von {total_candles}"
            st.info(debug_info)

        st.subheader(f"📊 Chart: {st.session_state.selected_symbol}")

        # Determine which data to use
        chart_data = None
        if st.session_state.debug_mode and st.session_state.debug_all_data:
            # Debug mode: use filtered data
            chart_data = filter_debug_data(
                st.session_state.debug_all_data,
                st.session_state.debug_start_date,
                st.session_state.debug_current_index
            )
        elif st.session_state.live_data:
            # Normal mode: use live data
            chart_data = st.session_state.live_data

        if chart_data:
            chart_html = create_trading_chart(
                chart_data,
                trades=st.session_state.trades,
                selected_symbol=st.session_state.selected_symbol,
                selected_interval=st.session_state.selected_interval
            )
            st.components.v1.html(chart_html, height=450)

            # Debug Controls (only in debug mode)
            if st.session_state.debug_mode:
                st.markdown("### 🎮 Debug Controls")

                debug_col1, debug_col2, debug_col3, debug_col4 = st.columns([2, 2, 2, 2])

                with debug_col1:
                    # Next Button
                    if st.button("➡️ Next Kerze", key="debug_next", use_container_width=True):
                        if st.session_state.debug_all_data:
                            max_index = len(st.session_state.debug_all_data['data']) - 1
                            if st.session_state.debug_current_index < max_index:
                                st.session_state.debug_current_index += 1
                                st.rerun()

                with debug_col2:
                    # Play/Pause Button
                    play_text = "⏸️ Pause" if st.session_state.debug_play_mode else "▶️ Play"
                    if st.button(play_text, key="debug_play", use_container_width=True):
                        st.session_state.debug_play_mode = not st.session_state.debug_play_mode
                        st.rerun()

                with debug_col3:
                    # Speed Control
                    speed_options = [0.5, 1.0, 2.0, 5.0, 10.0]
                    speed_labels = ["0.5x", "1x", "2x", "5x", "10x"]
                    current_speed_index = speed_options.index(st.session_state.debug_speed) if st.session_state.debug_speed in speed_options else 1

                    new_speed_index = st.selectbox(
                        "Speed",
                        range(len(speed_options)),
                        index=current_speed_index,
                        format_func=lambda x: speed_labels[x],
                        key="debug_speed_select"
                    )
                    st.session_state.debug_speed = speed_options[new_speed_index]

                with debug_col4:
                    # Progress info
                    if st.session_state.debug_all_data:
                        progress = (st.session_state.debug_current_index + 1) / len(st.session_state.debug_all_data['data'])
                        st.metric("Progress", f"{progress:.1%}")

        else:
            st.info("Keine Daten geladen. Klicke auf 'Daten aktualisieren'")

    with col2:
        st.subheader("💼 Trading")

        if st.session_state.live_data:
            current_price = st.session_state.live_data['current_price']
            st.metric("Aktueller Preis", f"${current_price:.2f}")

            # Trading buttons
            col_buy, col_sell = st.columns(2)

            with col_buy:
                if st.button("🟢 BUY", key="buy_btn", use_container_width=True):
                    add_trade('BUY', current_price, 'Human')
                    st.success(f"BUY @ ${current_price:.2f}")

            with col_sell:
                if st.button("🔴 SELL", key="sell_btn", use_container_width=True):
                    add_trade('SELL', current_price, 'Human')
                    st.success(f"SELL @ ${current_price:.2f}")

        # Display trades
        display_trades()

        # Trade Statistics
        stats = get_trade_stats()
        if stats:
            st.subheader("📈 Statistiken")
            st.write(f"Total Trades: {stats['total']}")
            st.write(f"Human: {stats['human']}")
            st.write(f"AI: {stats['ai']}")

    # Auto-refresh and Debug Auto-Play
    if st.session_state.auto_refresh:
        time.sleep(2)
        st.rerun()

    # Debug Auto-Play Logic
    if st.session_state.debug_mode and st.session_state.debug_play_mode:
        # Calculate delay based on speed (lower speed = longer delay)
        delay = 2.0 / st.session_state.debug_speed  # Base delay of 2 seconds at 1x speed

        # Auto-advance to next candle
        if st.session_state.debug_all_data:
            max_index = len(st.session_state.debug_all_data['data']) - 1
            if st.session_state.debug_current_index < max_index:
                # Use a short sleep and rerun for auto-play
                time.sleep(delay)
                st.session_state.debug_current_index += 1
                st.rerun()
            else:
                # End of data reached, stop auto-play
                st.session_state.debug_play_mode = False
                st.rerun()

if __name__ == "__main__":
    main()