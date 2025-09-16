"""
Voll funktionsfähige TradingView App mit echten Live-Daten
Fehler-freie Version
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime, timedelta
import time

st.set_page_config(
    page_title="Trading App - Live Data",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Styling
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
</style>
""", unsafe_allow_html=True)

# Initialize session state
def init_session_state():
    defaults = {
        'live_data': None,
        'last_update': None,
        'auto_refresh': False,
        'selected_symbol': 'AAPL',
        'selected_interval': '5m',
        'trading_active': False,
        'human_feedback': []
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def get_yfinance_data(symbol, period="1d", interval="5m"):
    """Hole Live-Daten von Yahoo Finance - KORRIGIERTE VERSION"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return None

        # WICHTIG: Timezone-Handling für TradingView Lightweight Charts
        if hist.index.tz is not None:
            # Konvertiere zu UTC falls nötig
            hist.index = hist.index.tz_convert('UTC')
            # Entferne timezone info (wird als naive datetime gespeichert)
            hist.index = hist.index.tz_localize(None)

        # Sicherstellen dass wir naive datetime haben
        hist = hist.round(2)

        # DEBUG: Print timezone info
        print(f"DEBUG: Index timezone after processing: {hist.index.tz}")
        print(f"DEBUG: Sample timestamp: {hist.index[0]} -> {int(hist.index[0].timestamp())}")

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
        st.error(f"Fehler beim Laden der Daten: {e}")
        print(f"DEBUG: yfinance error: {e}")
        return None

def get_tradingview_widget(symbol, interval="5", height=600):
    """TradingView Widget"""
    tv_symbols = {
        'AAPL': 'NASDAQ:AAPL',
        'MSFT': 'NASDAQ:MSFT',
        'GOOGL': 'NASDAQ:GOOGL',
        'TSLA': 'NASDAQ:TSLA',
        'BTC-USD': 'BINANCE:BTCUSDT',
        'ETH-USD': 'BINANCE:ETHUSDT',
        'EURUSD=X': 'FX:EURUSD',
        '^GSPC': 'SP:SPX'
    }

    tv_symbol = tv_symbols.get(symbol, f"NASDAQ:{symbol}")

    widget_html = f"""
    <div style="width: 100%; height: {height}px; background-color: #131722; border-radius: 8px;">
      <div id="tradingview_chart" style="height: {height}px;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "width": "100%",
          "height": "{height}",
          "symbol": "{tv_symbol}",
          "interval": "{interval}",
          "timezone": "Etc/UTC",
          "theme": "dark",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#131722",
          "enable_publishing": false,
          "hide_top_toolbar": false,
          "container_id": "tradingview_chart",
          "studies": [
            "MASimple@tv-basicstudies"
          ]
        }});
      </script>
    </div>
    """
    return widget_html

def create_lightweight_chart(data_dict):
    """Lightweight Chart mit yfinance Daten - KORRIGIERTE VERSION"""
    if not data_dict or data_dict['data'].empty:
        return "<div>Keine Daten verfügbar</div>"

    df = data_dict['data']
    chart_data = []

    # DEBUG: Print first few timestamps to check format
    print(f"DEBUG: DataFrame index type: {type(df.index[0])}")
    print(f"DEBUG: First timestamp: {df.index[0]}")

    for idx, row in df.iterrows():
        # KRITISCH: TradingView braucht SEKUNDEN, nicht Millisekunden!
        # Und muss UTC-konform sein
        unix_timestamp = int(idx.timestamp())  # Das ist bereits in Sekunden!

        chart_data.append({
            'time': unix_timestamp,  # UTC timestamp in SEKUNDEN
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row['Volume'])
        })

    # DEBUG: Print sample data
    if chart_data:
        print(f"DEBUG: Sample chart data: {chart_data[0]}")
        print(f"DEBUG: Total data points: {len(chart_data)}")

    js_data = json.dumps(chart_data)

    widget_html = f"""
    <div style="width: 100%; height: 600px; background-color: #131722; border-radius: 8px;">
      <div id="lightweight_chart" style="height: 600px;"></div>
      <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
      <script type="text/javascript">
        console.log('Loading TradingView Lightweight Charts...');
        console.log('Chart data:', {js_data});

        const chartContainer = document.getElementById('lightweight_chart');

        if (!chartContainer) {{
          console.error('Chart container not found!');
        }}

        // Warte bis Library geladen ist
        if (typeof LightweightCharts === 'undefined') {{
          console.error('LightweightCharts library not loaded!');
          return;
        }}

        console.log('LightweightCharts version:', LightweightCharts.version || 'unknown');

        const chart = LightweightCharts.createChart(chartContainer, {{
          width: chartContainer.offsetWidth,
          height: 600,
          layout: {{
            backgroundColor: '#131722',
            textColor: '#d9d9d9',
          }},
          grid: {{
            vertLines: {{
              color: '#2B2B43',
            }},
            horzLines: {{
              color: '#2B2B43',
            }},
          }},
          crosshair: {{
            mode: LightweightCharts.CrosshairMode.Normal,
          }},
          rightPriceScale: {{
            borderColor: '#485c7b',
          }},
          timeScale: {{
            borderColor: '#485c7b',
            timeVisible: true,
            secondsVisible: false,
          }},
        }});

        console.log('Chart created successfully');
        console.log('Available chart methods:', Object.getOwnPropertyNames(chart));

        const candlestickSeries = chart.addCandlestickSeries({{
          upColor: '#26a69a',
          downColor: '#ef5350',
          borderVisible: false,
          wickUpColor: '#26a69a',
          wickDownColor: '#ef5350',
        }});

        console.log('Candlestick series added');

        try {{
          const chartData = {js_data};
          console.log('Setting chart data:', chartData.length, 'points');

          if (chartData && chartData.length > 0) {{
            candlestickSeries.setData(chartData);
            console.log('Chart data set successfully');

            // Auto-fit chart
            chart.timeScale().fitContent();
          }} else {{
            console.error('No chart data available');
          }}
        }} catch (error) {{
          console.error('Error setting chart data:', error);
        }}

        // Auto-resize
        window.addEventListener('resize', () => {{
          chart.applyOptions({{ width: chartContainer.offsetWidth }});
        }});

        console.log('Chart setup complete');
      </script>
    </div>
    """
    return widget_html

def format_number(value):
    """Sichere Zahlenformatierung"""
    if isinstance(value, (int, float)) and not pd.isna(value):
        if value >= 1e9:
            return f"{value/1e9:.2f}B"
        elif value >= 1e6:
            return f"{value/1e6:.2f}M"
        elif value >= 1e3:
            return f"{value/1e3:.2f}K"
        else:
            return f"{value:,.0f}"
    return "N/A"

def main():
    init_session_state()

    st.title("📈 Live Trading Dashboard")

    # Sidebar
    with st.sidebar:
        st.header("🎛️ Controls")

        # Symbol Selection
        symbol_categories = {
            "🏢 US Stocks": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"],
            "💰 Crypto": ["BTC-USD", "ETH-USD"],
            "💱 Forex": ["EURUSD=X"],
            "📊 Indices": ["^GSPC"]
        }

        selected_category = st.selectbox("Kategorie", list(symbol_categories.keys()))
        selected_symbol = st.selectbox("Symbol", symbol_categories[selected_category])

        if selected_symbol != st.session_state.selected_symbol:
            st.session_state.selected_symbol = selected_symbol
            st.session_state.live_data = None

        # Timeframe
        interval_options = {
            "1 Minute": "1m",
            "5 Minuten": "5m",
            "15 Minuten": "15m",
            "1 Stunde": "1h"
        }
        selected_interval_name = st.selectbox("Timeframe", list(interval_options.keys()), index=1)
        st.session_state.selected_interval = interval_options[selected_interval_name]

        # Chart Type
        chart_type = st.radio("Chart Type",
                             ["TradingView Widget (Live)", "yfinance + Lightweight Charts"])

        st.markdown("---")

        # Controls
        if st.button("🔄 Daten Aktualisieren", type="primary"):
            st.session_state.live_data = None
            st.rerun()

        st.session_state.auto_refresh = st.checkbox("🔄 Auto-Refresh (30s)")

        if st.button("🚀 Trading Session"):
            st.session_state.trading_active = not st.session_state.trading_active

        # Status
        st.markdown("---")
        st.write(f"**Symbol:** {st.session_state.selected_symbol}")
        st.write(f"**Timeframe:** {selected_interval_name}")
        st.write(f"**Trading:** {'🟢' if st.session_state.trading_active else '🔴'}")

        if st.session_state.last_update:
            st.write(f"**Update:** {st.session_state.last_update.strftime('%H:%M:%S')}")

    # Main Content
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📊 {st.session_state.selected_symbol} Chart")

        if chart_type.startswith("TradingView Widget"):
            # TradingView Widget
            widget_html = get_tradingview_widget(
                st.session_state.selected_symbol,
                st.session_state.selected_interval
            )
            st.components.v1.html(widget_html, height=620)

        else:
            # yfinance + Lightweight Charts
            if st.session_state.live_data is None:
                with st.spinner("Loading..."):
                    period = "5d" if st.session_state.selected_interval in ["1m", "5m"] else "1mo"
                    st.session_state.live_data = get_yfinance_data(
                        st.session_state.selected_symbol,
                        period=period,
                        interval=st.session_state.selected_interval
                    )
                    st.session_state.last_update = datetime.now()

            if st.session_state.live_data:
                chart_html = create_lightweight_chart(st.session_state.live_data)
                st.components.v1.html(chart_html, height=620)
            else:
                st.error("Keine Daten verfügbar")

    with col2:
        st.subheader("📊 Live Data")

        if st.session_state.live_data:
            data = st.session_state.live_data

            # Current Price
            current_price = data['current_price']
            last_close = data['data']['Close'].iloc[-2] if len(data['data']) > 1 else current_price
            price_change = current_price - last_close
            price_change_pct = (price_change / last_close) * 100

            color_class = "status-good" if price_change >= 0 else "status-bad"

            st.markdown(f"""
            <div class="data-panel">
                <h4>💰 Aktueller Kurs</h4>
                <div class="metric-card">
                    <h2 class="{color_class}">${current_price:.2f}</h2>
                    <p class="{color_class}">
                        {'+' if price_change >= 0 else ''}{price_change:.2f}
                        ({'+' if price_change_pct >= 0 else ''}{price_change_pct:.2f}%)
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Market Info
            if 'info' in data and data['info']:
                info = data['info']

                volume = format_number(info.get('volume'))
                market_cap = format_number(info.get('marketCap'))

                st.markdown(f"""
                <div class="data-panel">
                    <h4>📈 Marktdaten</h4>
                    <div class="metric-card">
                        <p><strong>Volumen:</strong> {volume}</p>
                        <p><strong>Market Cap:</strong> {market_cap}</p>
                        <p><strong>52W High:</strong> ${info.get('fiftyTwoWeekHigh', 'N/A')}</p>
                        <p><strong>52W Low:</strong> ${info.get('fiftyTwoWeekLow', 'N/A')}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # AI Trading
        if st.session_state.trading_active:
            st.markdown("""
            <div class="data-panel">
                <h4>🤖 AI Trading</h4>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.live_data:
                data = st.session_state.live_data['data']
                if len(data) >= 20:
                    ma20 = data['Close'].rolling(20).mean().iloc[-1]
                    current = data['Close'].iloc[-1]

                    signal = "🟢 BUY" if current > ma20 else "🔴 SELL"
                    signal_class = "status-good" if current > ma20 else "status-bad"

                    st.markdown(f'<p class="{signal_class}"><strong>{signal}</strong></p>',
                               unsafe_allow_html=True)
                    st.write(f"MA20: ${ma20:.2f}")
                    st.write(f"Current: ${current:.2f}")

            # Feedback
            col_good, col_bad, col_neutral = st.columns(3)

            with col_good:
                if st.button("✅", key="good"):
                    st.session_state.human_feedback.append({
                        'time': datetime.now(),
                        'feedback': 'good',
                        'symbol': st.session_state.selected_symbol
                    })
                    st.success("✅")

            with col_bad:
                if st.button("❌", key="bad"):
                    st.session_state.human_feedback.append({
                        'time': datetime.now(),
                        'feedback': 'bad',
                        'symbol': st.session_state.selected_symbol
                    })
                    st.error("❌")

            with col_neutral:
                if st.button("⚪", key="neutral"):
                    st.session_state.human_feedback.append({
                        'time': datetime.now(),
                        'feedback': 'neutral',
                        'symbol': st.session_state.selected_symbol
                    })
                    st.info("⚪")

        else:
            st.info("🚀 Klicke 'Trading Session' für AI-Features")

    # Footer
    if st.session_state.human_feedback:
        st.markdown("---")
        feedback_df = pd.DataFrame(st.session_state.human_feedback)
        good = len(feedback_df[feedback_df['feedback'] == 'good'])
        bad = len(feedback_df[feedback_df['feedback'] == 'bad'])
        neutral = len(feedback_df[feedback_df['feedback'] == 'neutral'])
        st.write(f"**Feedback:** ✅ {good} | ❌ {bad} | ⚪ {neutral}")

    # Auto-refresh
    if st.session_state.auto_refresh and not chart_type.startswith("TradingView"):
        time.sleep(30)
        st.session_state.live_data = None
        st.rerun()

if __name__ == "__main__":
    main()