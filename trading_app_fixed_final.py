"""
FINAL VERSION - TradingView Lightweight Charts WORKING
Mit korrekter API und Library Version
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Trading App - FINAL",
    page_icon="📈",
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
</style>
""", unsafe_allow_html=True)

# Session State
if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = 'AAPL'
if 'live_data' not in st.session_state:
    st.session_state.live_data = None

def get_yfinance_data(symbol, period="1d", interval="5m"):
    """Hole Live-Daten von Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return None

        # Timezone handling
        if hist.index.tz is not None:
            hist.index = hist.index.tz_convert('UTC').tz_localize(None)

        hist = hist.round(2)
        info = ticker.info
        current_price = info.get('currentPrice', hist['Close'].iloc[-1])

        return {
            'data': hist,
            'current_price': current_price,
            'symbol': symbol,
            'info': info
        }

    except Exception as e:
        st.error(f"Fehler: {e}")
        return None

def create_working_lightweight_chart(data_dict):
    """WORKING TradingView Lightweight Charts Implementation"""
    if not data_dict or data_dict['data'].empty:
        return "<div>Keine Daten verfügbar</div>"

    df = data_dict['data']
    chart_data = []

    for idx, row in df.iterrows():
        # UTC timestamp in Sekunden (NICHT Millisekunden!)
        unix_timestamp = int(idx.timestamp())

        chart_data.append({
            'time': unix_timestamp,
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close'])
        })

    # Sort by time to ensure proper order
    chart_data.sort(key=lambda x: x['time'])

    js_data = json.dumps(chart_data)

    widget_html = f"""
    <div style="width: 100%; height: 600px; background-color: #131722; border-radius: 8px;">
      <div id="tv_chart" style="height: 600px;"></div>

      <!-- Load TradingView Lightweight Charts v4.1.3 -->
      <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>

      <script>
        (function() {{
          console.log('🚀 Loading TradingView Lightweight Charts...');

          // Wait for library to load
          if (typeof LightweightCharts === 'undefined') {{
            console.error('❌ LightweightCharts not loaded!');
            document.getElementById('tv_chart').innerHTML = '<div style="color: red; text-align: center; padding: 50px;">Error: TradingView Library not loaded</div>';
          }} else {{

          console.log('✅ LightweightCharts loaded, version:', LightweightCharts.version || 'unknown');

          const container = document.getElementById('tv_chart');
          if (!container) {{
            console.error('❌ Chart container not found!');
          }} else {{

          // Create chart with proper configuration
          const chart = LightweightCharts.createChart(container, {{
            width: container.offsetWidth,
            height: 600,
            layout: {{
              backgroundColor: '#131722',
              textColor: '#d9d9d9'
            }},
            grid: {{
              vertLines: {{ color: '#2B2B43' }},
              horzLines: {{ color: '#2B2B43' }}
            }},
            timeScale: {{
              timeVisible: true,
              secondsVisible: false,
              borderColor: '#485c7b'
            }},
            rightPriceScale: {{
              borderColor: '#485c7b'
            }}
          }});

          console.log('✅ Chart created');

          // Add candlestick series
          const candleSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderUpColor: '#26a69a',
            borderDownColor: '#ef5350',
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350'
          }});

          console.log('✅ Candlestick series added');

          // Set data
          const chartData = {js_data};
          console.log('📊 Setting data:', chartData.length, 'points');
          console.log('📊 First data point:', chartData[0]);
          console.log('📊 Last data point:', chartData[chartData.length - 1]);

          if (chartData && chartData.length > 0) {{
            candleSeries.setData(chartData);
            console.log('✅ Data set successfully');

            // Fit chart to content
            chart.timeScale().fitContent();
            console.log('✅ Chart fitted to content');
          }} else {{
            console.error('❌ No data to display');
          }}

          // Auto-resize
          window.addEventListener('resize', () => {{
            chart.applyOptions({{ width: container.offsetWidth }});
          }});

          console.log('🎉 Chart setup complete!');

          }} // Close container check
          }} // Close LightweightCharts check

        }})();
      </script>
    </div>
    """
    return widget_html

def get_tradingview_widget(symbol, interval="5"):
    """TradingView Widget als Fallback"""
    tv_symbols = {
        'AAPL': 'NASDAQ:AAPL',
        'MSFT': 'NASDAQ:MSFT',
        'GOOGL': 'NASDAQ:GOOGL',
        'TSLA': 'NASDAQ:TSLA',
        'BTC-USD': 'BINANCE:BTCUSDT',
        'ETH-USD': 'BINANCE:ETHUSDT'
    }

    tv_symbol = tv_symbols.get(symbol, f"NASDAQ:{symbol}")

    return f"""
    <div style="width: 100%; height: 600px; background-color: #131722;">
      <div id="tradingview_widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "width": "100%",
          "height": "600",
          "symbol": "{tv_symbol}",
          "interval": "{interval}",
          "timezone": "Etc/UTC",
          "theme": "dark",
          "style": "1",
          "locale": "en",
          "container_id": "tradingview_widget"
        }});
      </script>
    </div>
    """

def main():
    st.title("📈 TradingView Charts - FINAL VERSION")

    # Sidebar
    with st.sidebar:
        st.header("🎛️ Controls")

        # Symbol Selection
        symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "BTC-USD", "ETH-USD"]
        selected_symbol = st.selectbox("Symbol", symbols)

        if selected_symbol != st.session_state.selected_symbol:
            st.session_state.selected_symbol = selected_symbol
            st.session_state.live_data = None

        # Timeframe
        intervals = {"5 Min": "5m", "15 Min": "15m", "1 Hour": "1h"}
        interval_name = st.selectbox("Timeframe", list(intervals.keys()))
        interval = intervals[interval_name]

        # Chart Type
        chart_type = st.radio("Chart Type", [
            "🔥 Lightweight Charts (yfinance)",
            "📊 TradingView Widget (Live)"
        ])

        st.markdown("---")

        if st.button("🔄 Refresh Data", type="primary"):
            st.session_state.live_data = None
            st.rerun()

        # Status
        st.write(f"**Symbol:** {st.session_state.selected_symbol}")
        st.write(f"**Timeframe:** {interval_name}")
        st.write(f"**Chart:** {chart_type.split(' ')[1]}")

    # Main Content
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📊 {st.session_state.selected_symbol} Chart")

        if chart_type.startswith("🔥"):
            # Lightweight Charts with yfinance data
            if st.session_state.live_data is None:
                with st.spinner("Loading live data..."):
                    period = "5d" if interval in ["1m", "5m"] else "1mo"
                    st.session_state.live_data = get_yfinance_data(
                        st.session_state.selected_symbol,
                        period=period,
                        interval=interval
                    )

            if st.session_state.live_data:
                st.markdown("**🔥 TradingView Lightweight Charts mit echten yfinance Daten**")
                chart_html = create_working_lightweight_chart(st.session_state.live_data)
                st.components.v1.html(chart_html, height=620)

                # Debug info
                st.info(f"📊 {len(st.session_state.live_data['data'])} Datenpunkte geladen")
            else:
                st.error("❌ Keine Daten verfügbar")

        else:
            # TradingView Widget (always works)
            st.markdown("**📊 TradingView Widget (Live)**")
            widget_html = get_tradingview_widget(st.session_state.selected_symbol, interval)
            st.components.v1.html(widget_html, height=620)

    with col2:
        st.subheader("📊 Data")

        if st.session_state.live_data:
            data = st.session_state.live_data
            current_price = data['current_price']

            st.markdown(f"""
            <div class="data-panel">
                <h4>💰 Preis</h4>
                <div class="metric-card">
                    <h2 class="status-good">${current_price:.2f}</h2>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Market info
            if 'info' in data and data['info']:
                info = data['info']
                company = info.get('longName', 'N/A')
                volume = info.get('volume', 'N/A')

                st.markdown(f"""
                <div class="data-panel">
                    <h4>📈 Info</h4>
                    <div class="metric-card">
                        <p><strong>{company}</strong></p>
                        <p>Volumen: {volume:,}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown("**🔧 Debug:** Öffne F12 → Console für detaillierte Chart-Logs")

if __name__ == "__main__":
    main()