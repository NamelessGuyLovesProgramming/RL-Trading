"""
Funktionierende TradingView Integration mit echten Marktdaten
Kombiniert kostenlose TradingView Widgets mit yfinance Live-Daten
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime, timedelta
import time
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

st.set_page_config(
    page_title="🚀 RL Trading - Live TradingView",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for TradingView styling
st.markdown("""
<style>
.stApp {
    background-color: #0E1111;
    color: #d1d4dc;
}
.main .block-container {
    padding: 0rem 1rem;
    max-width: none;
}
.tradingview-widget-container {
    width: 100%;
    height: 600px;
    background-color: #131722;
    border-radius: 8px;
    margin: 1rem 0;
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
        'data_source': 'yfinance',
        'trading_active': False,
        'ai_trades': [],
        'human_feedback': []
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def get_yfinance_data(symbol, period="1d", interval="5m"):
    """Hole Live-Daten von Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)

        # Hole historische Daten
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            st.error(f"Keine Daten für {symbol} gefunden")
            return None

        # Konvertiere zu unserem Format
        hist.index = hist.index.tz_localize(None)  # Remove timezone
        hist = hist.round(2)

        # Füge aktuelle Info hinzu
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
        return None

def get_tradingview_widget(symbol, interval="5", theme="dark", height=600):
    """Erstelle TradingView Widget mit echten Live-Daten"""

    # TradingView Symbol mapping
    tv_symbols = {
        'AAPL': 'NASDAQ:AAPL',
        'MSFT': 'NASDAQ:MSFT',
        'GOOGL': 'NASDAQ:GOOGL',
        'TSLA': 'NASDAQ:TSLA',
        'BTC-USD': 'BINANCE:BTCUSDT',
        'ETH-USD': 'BINANCE:ETHUSDT',
        'EURUSD=X': 'FX:EURUSD',
        'GBPUSD=X': 'FX:GBPUSD',
        '^GSPC': 'SP:SPX',
        '^IXIC': 'NASDAQ:NDX'
    }

    tv_symbol = tv_symbols.get(symbol, f"NASDAQ:{symbol}")

    widget_html = f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart" style="height: {height}px;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "width": "100%",
          "height": "{height}",
          "symbol": "{tv_symbol}",
          "interval": "{interval}",
          "timezone": "Etc/UTC",
          "theme": "{theme}",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#131722",
          "enable_publishing": false,
          "hide_top_toolbar": false,
          "hide_legend": false,
          "save_image": false,
          "container_id": "tradingview_chart",
          "show_popup_button": false,
          "studies": [
            "MASimple@tv-basicstudies",
            "RSI@tv-basicstudies"
          ],
          "disabled_features": [
            "use_localstorage_for_settings"
          ],
          "enabled_features": [
            "study_templates"
          ]
        }});
      </script>
    </div>
    """
    return widget_html

def create_lightweight_chart_with_data(data_dict):
    """Erstelle Lightweight Chart mit echten yfinance Daten"""
    if not data_dict or data_dict['data'].empty:
        return "<div>Keine Daten verfügbar</div>"

    df = data_dict['data']

    # Konvertiere zu JavaScript Format
    chart_data = []
    for idx, row in df.iterrows():
        timestamp = int(idx.timestamp())
        chart_data.append({
            'time': timestamp,
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close']),
            'volume': float(row['Volume'])
        })

    js_data = json.dumps(chart_data)

    widget_html = f"""
    <div class="tradingview-widget-container">
      <div id="lightweight_chart" style="height: 600px; background-color: #131722;"></div>

      <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
      <script type="text/javascript">
        const chartContainer = document.getElementById('lightweight_chart');

        const chart = LightweightCharts.createChart(chartContainer, {{
          width: chartContainer.offsetWidth,
          height: 600,
          layout: {{
            background: {{ color: '#131722' }},
            textColor: '#d9d9d9',
          }},
          grid: {{
            vertLines: {{ color: '#2B2B43' }},
            horzLines: {{ color: '#2B2B43' }},
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

        // Candlestick series
        const candlestickSeries = chart.addCandlestickSeries({{
          upColor: '#26a69a',
          downColor: '#ef5350',
          borderVisible: false,
          wickUpColor: '#26a69a',
          wickDownColor: '#ef5350',
        }});

        // Set data
        const chartData = {js_data};
        candlestickSeries.setData(chartData);

        // Add volume series
        const volumeSeries = chart.addHistogramSeries({{
          color: '#26a69a',
          priceFormat: {{
            type: 'volume',
          }},
          priceScaleId: '',
          scaleMargins: {{
            top: 0.8,
            bottom: 0,
          }},
        }});

        const volumeData = chartData.map(d => ({{
          time: d.time,
          value: d.volume,
          color: d.close >= d.open ? '#26a69a80' : '#ef535080'
        }}));

        volumeSeries.setData(volumeData);

        // Auto-resize
        window.addEventListener('resize', () => {{
          chart.applyOptions({{ width: chartContainer.offsetWidth }});
        }});

        // Auto-scroll to latest data
        chart.timeScale().scrollToRealTime();
      </script>
    </div>
    """
    return widget_html

def main():
    init_session_state()

    st.title("🚀 RL Trading System - Live TradingView Integration")

    # Sidebar Controls
    with st.sidebar:
        st.header("🎛️ Trading Controls")

        # Symbol Selection
        symbol_categories = {
            "🏢 US Stocks": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA"],
            "💰 Crypto": ["BTC-USD", "ETH-USD"],
            "💱 Forex": ["EURUSD=X", "GBPUSD=X"],
            "📊 Indices": ["^GSPC", "^IXIC"]
        }

        selected_category = st.selectbox("Kategorie", list(symbol_categories.keys()))
        selected_symbol = st.selectbox("Symbol", symbol_categories[selected_category])

        if selected_symbol != st.session_state.selected_symbol:
            st.session_state.selected_symbol = selected_symbol
            st.session_state.live_data = None  # Reset data

        # Timeframe Selection
        interval_options = {
            "1 Minute": "1m",
            "5 Minuten": "5m",
            "15 Minuten": "15m",
            "30 Minuten": "30m",
            "1 Stunde": "1h",
            "1 Tag": "1d"
        }

        selected_interval_name = st.selectbox("Timeframe", list(interval_options.keys()), index=1)
        st.session_state.selected_interval = interval_options[selected_interval_name]

        # Data Source
        data_source = st.radio("Datenquelle",
                              ["TradingView Widget (Live)", "yfinance + Lightweight Charts"],
                              index=0)
        st.session_state.data_source = data_source

        st.markdown("---")

        # Auto-refresh
        st.session_state.auto_refresh = st.checkbox("🔄 Auto-Refresh (30s)", value=False)

        if st.button("🔄 Daten Aktualisieren", type="primary"):
            st.session_state.live_data = None
            st.rerun()

        st.markdown("---")

        # Trading Session
        if st.button("🚀 Trading Session Starten"):
            st.session_state.trading_active = True
            st.success("Trading Session aktiv!")

        if st.session_state.trading_active:
            if st.button("⏸️ Session Pausieren"):
                st.session_state.trading_active = False
                st.info("Session pausiert")

        st.markdown("---")

        # Status Info
        st.subheader("📊 Status")
        st.write(f"**Symbol:** {st.session_state.selected_symbol}")
        st.write(f"**Timeframe:** {selected_interval_name}")
        st.write(f"**Datenquelle:** {st.session_state.data_source.split(' ')[0]}")

        if st.session_state.last_update:
            st.write(f"**Letzte Aktualisierung:** {st.session_state.last_update.strftime('%H:%M:%S')}")

        st.write(f"**Trading:** {'🟢 Aktiv' if st.session_state.trading_active else '🔴 Inaktiv'}")

    # Main Content
    col1, col2 = st.columns([4, 1])

    with col1:
        st.subheader(f"📈 {st.session_state.selected_symbol} Chart")

        if st.session_state.data_source.startswith("TradingView Widget"):
            # Use TradingView Widget (always live)
            widget_html = get_tradingview_widget(
                st.session_state.selected_symbol,
                st.session_state.selected_interval,
                "dark"
            )
            st.components.v1.html(widget_html, height=620)

        else:
            # Use yfinance + Lightweight Charts
            if st.session_state.live_data is None:
                with st.spinner("Lade Live-Daten..."):
                    period = "5d" if st.session_state.selected_interval in ["1m", "5m"] else "1mo"
                    st.session_state.live_data = get_yfinance_data(
                        st.session_state.selected_symbol,
                        period=period,
                        interval=st.session_state.selected_interval
                    )
                    st.session_state.last_update = datetime.now()

            if st.session_state.live_data:
                chart_html = create_lightweight_chart_with_data(st.session_state.live_data)
                st.components.v1.html(chart_html, height=620)
            else:
                st.error("Keine Daten verfügbar. Bitte anderen Timeframe oder Symbol versuchen.")

    with col2:
        st.subheader("📊 Live Data")

        if st.session_state.live_data:
            data = st.session_state.live_data

            # Current Price
            current_price = data['current_price']
            last_close = data['data']['Close'].iloc[-2] if len(data['data']) > 1 else current_price
            price_change = current_price - last_close
            price_change_pct = (price_change / last_close) * 100

            # Price Display
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

            # Market Data
            if 'info' in data and data['info']:
                info = data['info']

                # Safe formatting for numbers
                volume = info.get('volume', 'N/A')
                volume_str = f"{volume:,}" if isinstance(volume, (int, float)) else str(volume)

                market_cap = info.get('marketCap', 'N/A')
                market_cap_str = f"{market_cap:,}" if isinstance(market_cap, (int, float)) else str(market_cap)

                fifty_two_high = info.get('fiftyTwoWeekHigh', 'N/A')
                fifty_two_low = info.get('fiftyTwoWeekLow', 'N/A')

                st.markdown(f"""
                <div class="data-panel">
                    <h4>📈 Marktdaten</h4>
                    <div class="metric-card">
                        <p><strong>Volumen:</strong> {volume_str}</p>
                        <p><strong>Marktkapitalisierung:</strong> {market_cap_str}</p>
                        <p><strong>52W High:</strong> ${fifty_two_high}</p>
                        <p><strong>52W Low:</strong> ${fifty_two_low}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # AI Trading Panel
        if st.session_state.trading_active:
            st.markdown("""
            <div class="data-panel">
                <h4>🤖 AI Trading</h4>
            </div>
            """, unsafe_allow_html=True)

            # Simple AI Logic
            if st.session_state.live_data:
                data = st.session_state.live_data['data']
                if len(data) >= 20:
                    ma20 = data['Close'].rolling(20).mean().iloc[-1]
                    current = data['Close'].iloc[-1]

                    if current > ma20:
                        signal = "🟢 BUY Signal"
                        signal_class = "status-good"
                    else:
                        signal = "🔴 SELL Signal"
                        signal_class = "status-bad"

                    st.markdown(f'<p class="{signal_class}"><strong>{signal}</strong></p>', unsafe_allow_html=True)
                    st.write(f"MA20: ${ma20:.2f}")
                    st.write(f"Current: ${current:.2f}")

            # Feedback Buttons
            col_buy, col_sell, col_hold = st.columns(3)

            with col_buy:
                if st.button("✅ Good", key="good"):
                    st.session_state.human_feedback.append({
                        'timestamp': datetime.now(),
                        'feedback': 'good',
                        'symbol': st.session_state.selected_symbol
                    })
                    st.success("Feedback ✅")

            with col_sell:
                if st.button("❌ Bad", key="bad"):
                    st.session_state.human_feedback.append({
                        'timestamp': datetime.now(),
                        'feedback': 'bad',
                        'symbol': st.session_state.selected_symbol
                    })
                    st.error("Feedback ❌")

            with col_hold:
                if st.button("⚪ Neutral", key="neutral"):
                    st.session_state.human_feedback.append({
                        'timestamp': datetime.now(),
                        'feedback': 'neutral',
                        'symbol': st.session_state.selected_symbol
                    })
                    st.info("Feedback ⚪")
        else:
            st.info("🚀 Starte Trading Session für AI-Features")

    # Footer Info
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**🔗 Datenquellen:**")
        st.markdown("- TradingView (Live Charts)")
        st.markdown("- Yahoo Finance (yfinance)")

    with col2:
        st.markdown("**⚡ Features:**")
        st.markdown("- Live Marktdaten")
        st.markdown("- Interaktive Charts")
        st.markdown("- AI Trading Signals")

    with col3:
        if st.session_state.human_feedback:
            st.markdown("**📊 Feedback Stats:**")
            feedback_df = pd.DataFrame(st.session_state.human_feedback)
            good_count = len(feedback_df[feedback_df['feedback'] == 'good'])
            bad_count = len(feedback_df[feedback_df['feedback'] == 'bad'])
            neutral_count = len(feedback_df[feedback_df['feedback'] == 'neutral'])
            st.markdown(f"✅ Good: {good_count} | ❌ Bad: {bad_count} | ⚪ Neutral: {neutral_count}")

    # Auto-refresh
    if st.session_state.auto_refresh and st.session_state.data_source.startswith("yfinance"):
        time.sleep(30)
        st.session_state.live_data = None
        st.rerun()

if __name__ == "__main__":
    main()