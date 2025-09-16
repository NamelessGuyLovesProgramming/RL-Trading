import streamlit as st
import sys
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.append('src')
from data_feed import create_sample_data

st.set_page_config(page_title="RL Trading - Simple Chart", layout="wide")

st.title("🚀 RL Trading System - Working Chart")

# Initialize session state
if 'current_step' not in st.session_state:
    st.session_state.current_step = 50
if 'trading_session_active' not in st.session_state:
    st.session_state.trading_session_active = False

# Sidebar
with st.sidebar:
    st.header("Trading Controls")

    # Symbol selection
    symbol_options = {"NQ": "NQ", "ES": "ES", "BTC": "BTC", "EUR": "EUR"}
    selected_symbol = st.selectbox("Symbol", list(symbol_options.keys()), index=0)

    # Step control
    st.session_state.current_step = st.slider("Current Step", 1, 200, st.session_state.current_step)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Previous"):
            st.session_state.current_step = max(1, st.session_state.current_step - 1)
            st.rerun()
    with col2:
        if st.button("➡️ Next"):
            st.session_state.current_step = min(200, st.session_state.current_step + 1)
            st.rerun()

    st.markdown("---")

    # Trading session
    if st.button("🚀 Start Trading Session", type="primary"):
        st.session_state.trading_session_active = True
        st.success("Session started!")

    if st.session_state.trading_session_active:
        if st.button("🛑 End Session"):
            st.session_state.trading_session_active = False
            st.info("Session ended")

    st.write(f"Current Step: {st.session_state.current_step}/200")

# Main area
col1, col2 = st.columns([4, 1])

with col1:
    st.subheader(f"📈 {selected_symbol} - Step {st.session_state.current_step}")

    try:
        # Get data
        data = create_sample_data(selected_symbol, periods=200)
        data = data.reset_index(drop=True)

        # Show only data up to current step
        current_data = data.iloc[:st.session_state.current_step+1]

        # Create plotly chart
        fig = go.Figure(data=go.Candlestick(
            x=current_data.index,
            open=current_data['open'],
            high=current_data['high'],
            low=current_data['low'],
            close=current_data['close'],
            name=selected_symbol
        ))

        # Add MA20
        if len(current_data) >= 20:
            ma20 = current_data['close'].rolling(window=20).mean()
            fig.add_trace(go.Scatter(
                x=current_data.index,
                y=ma20,
                mode='lines',
                name='MA20',
                line=dict(color='yellow', width=2)
            ))

        # Highlight current candle
        current_candle = current_data.iloc[-1]
        fig.add_trace(go.Scatter(
            x=[st.session_state.current_step],
            y=[current_candle['close']],
            mode='markers',
            marker=dict(color='red', size=10, symbol='diamond'),
            name='Current Step'
        ))

        # Chart styling
        fig.update_layout(
            template='plotly_dark',
            height=600,
            xaxis_title="Step",
            yaxis_title="Price",
            showlegend=True,
            xaxis=dict(rangeslider=dict(visible=False))
        )

        # Focus on recent data
        if len(current_data) > 50:
            focus_start = max(0, st.session_state.current_step - 50)
            focus_end = st.session_state.current_step + 5
            fig.update_xaxes(range=[focus_start, focus_end])

        st.plotly_chart(fig, use_container_width=True)

        # Data info
        current_price = current_candle['close']
        prev_price = current_data.iloc[-2]['close'] if len(current_data) > 1 else current_price
        price_change = ((current_price - prev_price) / prev_price) * 100

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Current Price", f"${current_price:.2f}", f"{price_change:+.2f}%")
        with col_b:
            st.metric("Total Candles", len(current_data))
        with col_c:
            st.metric("Progress", f"{st.session_state.current_step}/200")

    except Exception as e:
        st.error(f"Chart error: {e}")

with col2:
    st.subheader("🧠 AI Feedback")

    if st.session_state.trading_session_active:
        # AI decision logic
        if 'current_price' in locals() and 'prev_price' in locals():
            if current_price > prev_price * 1.001:
                action = "BUY"
                color = "green"
            elif current_price < prev_price * 0.999:
                action = "SELL"
                color = "red"
            else:
                action = "HOLD"
                color = "gray"

            st.markdown(f"**Action:** :{color}[{action}]")
            st.write(f"Current: ${current_price:.2f}")
            st.write(f"Previous: ${prev_price:.2f}")

        st.markdown("---")
        st.write("**Rate this decision:**")

        col_good, col_bad = st.columns(2)
        with col_good:
            if st.button("✅ Good"):
                st.success("Feedback: Good")
        with col_bad:
            if st.button("❌ Bad"):
                st.error("Feedback: Bad")
    else:
        st.info("Start session for AI training")

# Auto refresh
if st.session_state.trading_session_active:
    import time
    time.sleep(1)
    if st.session_state.current_step < 200:
        st.session_state.current_step += 1
        st.rerun()