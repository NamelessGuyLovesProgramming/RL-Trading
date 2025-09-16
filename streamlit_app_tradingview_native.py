import streamlit as st
import sys
import os
import pandas as pd
import json
from datetime import datetime, timedelta
import time

# Add src to path for imports
sys.path.append('src')

from data_feed import create_sample_data

st.set_page_config(
    page_title="TradingView RL Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for TradingView styling
st.markdown("""
<style>
.stApp {
    background-color: #0E1111;
}
.main .block-container {
    padding: 0rem 1rem;
    max-width: none;
}
.tradingview-widget-container {
    width: 100%;
    height: 800px;
}
.control-panel {
    background-color: #1E2128;
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
}
.feedback-buttons {
    display: flex;
    gap: 10px;
    margin: 1rem 0;
}
.feedback-btn {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    font-weight: bold;
}
.good-btn { background-color: #26a69a; color: white; }
.bad-btn { background-color: #ef5350; color: white; }
.neutral-btn { background-color: #787b86; color: white; }
</style>
""", unsafe_allow_html=True)

def get_ai_training_data(symbol="NQ", current_step=100, num_candles=200):
    """Get AI training data for the chart"""
    try:
        data = create_sample_data(symbol, periods=num_candles)
        # Reset index to ensure we have integer indices
        data = data.reset_index(drop=True)

        # Convert to format suitable for chart display
        chart_data = []
        for idx in range(len(data)):
            row = data.iloc[idx]
            chart_data.append({
                'time': idx,  # Use integer index
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume', 1000))
            })
        return chart_data[:current_step+1]  # Only show up to current step
    except Exception as e:
        st.error(f"Error loading training data: {e}")
        return []

def get_tradingview_widget_with_data(symbol="NQ", interval="5", theme="dark", current_step=100):
    """Generate TradingView widget with AI training data"""

    # Get AI training data
    training_data = get_ai_training_data(symbol, current_step)

    if not training_data:
        # Fallback to live TradingView data if no training data
        return get_tradingview_widget_live(symbol, interval, theme)

    # Convert training data to JavaScript array format
    js_data = json.dumps(training_data)

    widget_html = f"""
    <!-- TradingView Widget with AI Training Data -->
    <div class="tradingview-widget-container">
      <div id="ai_training_chart" style="height: 800px; background-color: #131722;"></div>

      <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
      <script type="text/javascript">
        // Create lightweight chart with AI training data
        const chartContainer = document.getElementById('ai_training_chart');
        const chart = LightweightCharts.createChart(chartContainer, {{
          width: chartContainer.offsetWidth,
          height: 800,
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
            timeVisible: false,
            secondsVisible: false,
          }},
        }});

        // Add candlestick series
        const candlestickSeries = chart.addCandlestickSeries({{
          upColor: '#26a69a',
          downColor: '#ef5350',
          borderVisible: false,
          wickUpColor: '#26a69a',
          wickDownColor: '#ef5350',
        }});

        // Set AI training data
        const trainingData = {js_data};
        candlestickSeries.setData(trainingData);

        // Add current step marker
        const currentStep = {current_step};
        if (currentStep < trainingData.length) {{
          const currentBar = trainingData[currentStep];
          // Highlight current candle
          chart.addLineSeries({{
            color: '#ffeb3b',
            lineWidth: 3,
          }}).setData([
            {{ time: currentBar.time, value: currentBar.close }}
          ]);
        }}

        // Add simple moving average
        const ma20Data = [];
        let sum = 0;
        for (let i = 0; i < trainingData.length; i++) {{
          sum += trainingData[i].close;
          if (i >= 19) {{
            if (i > 19) sum -= trainingData[i-20].close;
            ma20Data.push({{
              time: trainingData[i].time,
              value: sum / Math.min(i+1, 20)
            }});
          }}
        }}

        const maSeries = chart.addLineSeries({{
          color: '#ffeb3b',
          lineWidth: 2,
        }});
        maSeries.setData(ma20Data);

        // Auto-resize
        window.addEventListener('resize', () => {{
          chart.applyOptions({{ width: chartContainer.offsetWidth }});
        }});

        // Focus on current step
        if (trainingData.length > 0) {{
          const focusStart = Math.max(0, currentStep - 50);
          const focusEnd = Math.min(trainingData.length - 1, currentStep + 10);
          chart.timeScale().setVisibleRange({{
            from: trainingData[focusStart].time,
            to: trainingData[focusEnd].time,
          }});
        }}
      </script>
    </div>
    """
    return widget_html

def get_tradingview_widget_live(symbol="NAS100", interval="5", theme="dark"):
    """Generate TradingView widget with live data (fallback)"""
    widget_html = f"""
    <!-- TradingView Widget with Live Data -->
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "width": "100%",
          "height": "800",
          "symbol": "OANDA:{symbol}",
          "interval": "{interval}",
          "timezone": "exchange",
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
          "popup_width": "1000",
          "popup_height": "650",
          "studies": [
            "MASimple@tv-basicstudies",
            "BollingerBands@tv-basicstudies"
          ],
          "disabled_features": [
            "header_symbol_search",
            "header_screenshot",
            "header_chart_type",
            "header_compare",
            "header_undo_redo",
            "header_settings",
            "use_localstorage_for_settings"
          ],
          "enabled_features": [
            "study_templates",
            "side_toolbar_in_fullscreen_mode"
          ]
        }});
      </script>
    </div>
    """
    return widget_html

def main():
    st.title("🚀 RL Trading System - TradingView Integration")

    # Initialize session state
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 50
    if 'trading_session_active' not in st.session_state:
        st.session_state.trading_session_active = False
    if 'auto_play' not in st.session_state:
        st.session_state.auto_play = False
    if 'feedback_history' not in st.session_state:
        st.session_state.feedback_history = []
    if 'use_ai_data' not in st.session_state:
        st.session_state.use_ai_data = True

    # Sidebar Controls
    with st.sidebar:
        st.header("Trading Controls")

        # Data Source Selection
        st.session_state.use_ai_data = st.checkbox("Use AI Training Data", value=True,
                                                   help="Use controlled AI training data instead of live market data")

        # Symbol Selection
        if st.session_state.use_ai_data:
            ai_symbol_options = {
                "NQ (AI Training)": "NQ",
                "ES (AI Training)": "ES",
                "BTC (AI Training)": "BTC",
                "EUR (AI Training)": "EUR"
            }
            selected_symbol_name = st.selectbox("AI Training Symbol", list(ai_symbol_options.keys()), index=0)
            selected_symbol = ai_symbol_options[selected_symbol_name]
        else:
            symbol_options = {
                "NAS100": "NAS100",
                "EUR/USD": "EURUSD",
                "GBP/USD": "GBPUSD",
                "USD/JPY": "USDJPY",
                "BTC/USD": "BTCUSD",
                "Gold": "XAUUSD"
            }
            selected_symbol_name = st.selectbox("Live Market Symbol", list(symbol_options.keys()), index=0)
            selected_symbol = symbol_options[selected_symbol_name]

        # Timeframe Selection
        timeframe_options = {
            "1 Minute": "1",
            "5 Minutes": "5",
            "15 Minutes": "15",
            "30 Minutes": "30",
            "1 Hour": "60",
            "4 Hours": "240",
            "Daily": "D"
        }
        selected_timeframe_name = st.selectbox("Timeframe", list(timeframe_options.keys()), index=1)
        selected_timeframe = timeframe_options[selected_timeframe_name]

        st.markdown("---")

        # Trading Session Controls
        if st.button("🚀 Start Trading Session", type="primary"):
            st.session_state.trading_session_active = True
            st.success("Trading session started!")

        if st.session_state.trading_session_active:
            if st.button("⏸️ Pause Session"):
                st.session_state.auto_play = False
                st.info("Session paused")

            if st.button("▶️ Resume Auto-Play"):
                st.session_state.auto_play = True
                st.success("Auto-play resumed")

            if st.button("🛑 End Session", type="secondary"):
                st.session_state.trading_session_active = False
                st.session_state.auto_play = False
                st.info("Session ended")

        st.markdown("---")

        # AI Training Controls
        if st.session_state.use_ai_data:
            st.subheader("AI Training Step")
            new_step = st.slider("Current Step", 1, 200, st.session_state.current_step)
            if new_step != st.session_state.current_step:
                st.session_state.current_step = new_step

            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("⬅️ Previous"):
                    st.session_state.current_step = max(1, st.session_state.current_step - 1)
                    st.rerun()
            with col_next:
                if st.button("➡️ Next"):
                    st.session_state.current_step = min(200, st.session_state.current_step + 1)
                    st.rerun()

        st.markdown("---")

        # Current Status
        st.subheader("Session Status")
        st.write(f"Data Source: {'AI Training' if st.session_state.use_ai_data else 'Live Market'}")
        st.write(f"Symbol: {selected_symbol_name}")
        st.write(f"Timeframe: {selected_timeframe_name}")
        if st.session_state.use_ai_data:
            st.write(f"Current Step: {st.session_state.current_step}/200")
        st.write(f"Status: {'Active' if st.session_state.trading_session_active else 'Inactive'}")
        st.write(f"Auto-play: {'ON' if st.session_state.auto_play else 'OFF'}")

        # Feedback Stats
        if st.session_state.feedback_history:
            st.markdown("---")
            st.subheader("Feedback Stats")
            feedback_df = pd.DataFrame(st.session_state.feedback_history)
            good_count = len(feedback_df[feedback_df['feedback'] == 'good'])
            bad_count = len(feedback_df[feedback_df['feedback'] == 'bad'])
            neutral_count = len(feedback_df[feedback_df['feedback'] == 'neutral'])

            st.write(f"✅ Good: {good_count}")
            st.write(f"❌ Bad: {bad_count}")
            st.write(f"⚪ Neutral: {neutral_count}")

    # Main Content Area
    col1, col2 = st.columns([4, 1])

    with col1:
        if st.session_state.use_ai_data:
            st.subheader(f"📈 {selected_symbol_name} - AI Training Step {st.session_state.current_step}")
            # Display AI Training Data Chart
            widget_html = get_tradingview_widget_with_data(
                selected_symbol, selected_timeframe, "dark", st.session_state.current_step
            )
        else:
            st.subheader(f"📈 {selected_symbol_name} - {selected_timeframe_name} Chart")
            # Display Live TradingView widget
            widget_html = get_tradingview_widget_live(selected_symbol, selected_timeframe)

        st.components.v1.html(widget_html, height=820)

    with col2:
        st.subheader("🧠 AI Feedback")

        if st.session_state.trading_session_active:
            st.write("**Current AI Action:**")

            # Get AI decision based on current step and data
            import random
            random.seed(st.session_state.current_step)  # Consistent decisions based on step

            if st.session_state.use_ai_data:
                # Get current price data for AI decision
                try:
                    training_data = get_ai_training_data(selected_symbol, st.session_state.current_step)
                    if training_data:
                        current_price = training_data[-1]['close']
                        prev_price = training_data[-2]['close'] if len(training_data) > 1 else current_price

                        # Simple AI logic based on price movement
                        if current_price > prev_price * 1.001:
                            current_action = "BUY"
                        elif current_price < prev_price * 0.999:
                            current_action = "SELL"
                        else:
                            current_action = random.choice(["HOLD", "WAIT"])

                        st.write(f"Current Price: ${current_price:.2f}")
                        st.write(f"Previous Price: ${prev_price:.2f}")
                    else:
                        current_action = "WAIT"
                except:
                    current_action = "WAIT"
            else:
                # Random action for live data
                ai_actions = ["HOLD", "BUY", "SELL", "WAIT"]
                current_action = random.choice(ai_actions)

            if current_action == "BUY":
                st.success(f"📈 {current_action}")
            elif current_action == "SELL":
                st.error(f"📉 {current_action}")
            else:
                st.info(f"⏸️ {current_action}")

            st.markdown("---")
            st.write("**Rate this AI decision:**")

            # Feedback Buttons
            col_good, col_bad, col_neutral = st.columns(3)

            with col_good:
                if st.button("✅ Good", key="good_btn"):
                    feedback_data = {
                        'timestamp': datetime.now(),
                        'action': current_action,
                        'feedback': 'good',
                        'symbol': selected_symbol_name,
                        'timeframe': selected_timeframe_name
                    }
                    st.session_state.feedback_history.append(feedback_data)
                    st.success("Feedback recorded!")

            with col_bad:
                if st.button("❌ Bad", key="bad_btn"):
                    feedback_data = {
                        'timestamp': datetime.now(),
                        'action': current_action,
                        'feedback': 'bad',
                        'symbol': selected_symbol_name,
                        'timeframe': selected_timeframe_name
                    }
                    st.session_state.feedback_history.append(feedback_data)
                    st.error("Feedback recorded!")

            with col_neutral:
                if st.button("⚪ Neutral", key="neutral_btn"):
                    feedback_data = {
                        'timestamp': datetime.now(),
                        'action': current_action,
                        'feedback': 'neutral',
                        'symbol': selected_symbol_name,
                        'timeframe': selected_timeframe_name
                    }
                    st.session_state.feedback_history.append(feedback_data)
                    st.info("Feedback recorded!")

            st.markdown("---")

            # Recent Feedback History
            if st.session_state.feedback_history:
                st.write("**Recent Feedback:**")
                recent_feedback = st.session_state.feedback_history[-5:]  # Last 5 entries
                for i, feedback in enumerate(reversed(recent_feedback)):
                    timestamp = feedback['timestamp'].strftime("%H:%M:%S")
                    action = feedback['action']
                    rating = feedback['feedback']

                    if rating == 'good':
                        emoji = "✅"
                        color = "green"
                    elif rating == 'bad':
                        emoji = "❌"
                        color = "red"
                    else:
                        emoji = "⚪"
                        color = "gray"

                    st.write(f"{timestamp} - {action} {emoji}")
        else:
            st.info("Start a trading session to begin AI training")

    # Auto-refresh for auto-play mode
    if st.session_state.auto_play and st.session_state.use_ai_data:
        st.session_state.current_step = min(200, st.session_state.current_step + 1)
        time.sleep(2)  # Wait 2 seconds
        st.rerun()
    elif st.session_state.auto_play:
        time.sleep(2)  # Wait 2 seconds for live data
        st.rerun()

if __name__ == "__main__":
    main()