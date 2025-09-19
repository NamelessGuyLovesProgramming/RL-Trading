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
        'selected_symbol': 'AAPL',
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

        # Timezone handling für TradingView
        if hist.index.tz is not None:
            hist.index = hist.index.tz_convert('UTC').tz_localize(None)

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

    st.title("🚀 RL Trading - Clean Lightweight Charts")
    st.subheader("Simplified Working Version")

    # Sidebar
    st.sidebar.title("⚙️ Einstellungen")

    # Symbol Selection
    symbol_options = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'META']
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

    if st.sidebar.button("🔄 Daten aktualisieren") or st.session_state.auto_refresh:
        with st.spinner("Lade Daten..."):
            st.session_state.live_data = get_yfinance_data(
                st.session_state.selected_symbol,
                period="1d",
                interval=st.session_state.selected_interval
            )

    # Main content
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📊 Chart: {st.session_state.selected_symbol}")

        if st.session_state.live_data:
            chart_html = create_trading_chart(
                st.session_state.live_data,
                trades=st.session_state.trades,
                selected_symbol=st.session_state.selected_symbol,
                selected_interval=st.session_state.selected_interval
            )
            st.components.v1.html(chart_html, height=450)
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

    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(2)
        st.rerun()

if __name__ == "__main__":
    main()