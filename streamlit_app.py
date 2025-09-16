"""
Trackmania-Style Interactive RL Trading Dashboard
Live Chart Visualization mit Human-in-the-Loop Feedback
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from env import InteractiveTradingEnv
from agent import TradingPPOAgent, create_trading_agent
from data_feed import TradingDataManager, create_sample_data
from patterns import PatternManager

st.set_page_config(
    page_title="RL Trading - Trackmania Style",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'env' not in st.session_state:
    st.session_state.env = None
if 'agent' not in st.session_state:
    st.session_state.agent = None
if 'data' not in st.session_state:
    st.session_state.data = None
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'human_trades' not in st.session_state:
    st.session_state.human_trades = []
if 'ai_trades' not in st.session_state:
    st.session_state.ai_trades = []
if 'feedback_history' not in st.session_state:
    st.session_state.feedback_history = []
if 'tp_sl_boxes' not in st.session_state:
    st.session_state.tp_sl_boxes = []
if 'ai_trading_active' not in st.session_state:
    st.session_state.ai_trading_active = False
if 'show_tp_sl_tools' not in st.session_state:
    st.session_state.show_tp_sl_tools = False


def create_candlestick_chart(data: pd.DataFrame, patterns: dict = None, trades: list = None, tp_sl_boxes: list = None):
    """Create TradingView-style interactive candlestick chart"""

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.8, 0.2],
        subplot_titles=None  # Remove titles for cleaner look
    )

    # TradingView-style candlesticks
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            name="NQ",
            increasing_line_color='#26a69a',  # TradingView green
            decreasing_line_color='#ef5350',  # TradingView red
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350',
            line=dict(width=1),
            showlegend=False
        ),
        row=1, col=1
    )

    # Add pattern overlays
    if patterns:
        # FVG Zones
        if 'fvg_zones' in patterns:
            for zone in patterns['fvg_zones']:
                fig.add_shape(
                    type="rect",
                    x0=zone['start'], x1=zone['end'],
                    y0=zone['low'], y1=zone['high'],
                    fillcolor="rgba(255, 165, 0, 0.2)",
                    line=dict(color="orange", width=1),
                    name="FVG Zone",
                    row=1, col=1
                )

        # Order Blocks
        if 'order_blocks' in patterns:
            for block in patterns['order_blocks']:
                fig.add_shape(
                    type="rect",
                    x0=block['start'], x1=block['end'],
                    y0=block['low'], y1=block['high'],
                    fillcolor="rgba(0, 100, 255, 0.2)",
                    line=dict(color="blue", width=2),
                    name="Order Block",
                    row=1, col=1
                )

    # Add trades
    if trades:
        for trade in trades:
            color = '#00ff88' if trade['type'] == 'buy' else '#ff4444'
            symbol = '▲' if trade['type'] == 'buy' else '▼'

            fig.add_trace(
                go.Scatter(
                    x=[trade['timestamp']],
                    y=[trade['price']],
                    mode='markers+text',
                    marker=dict(
                        size=15,
                        color=color,
                        symbol='triangle-up' if trade['type'] == 'buy' else 'triangle-down'
                    ),
                    text=[f"{symbol} {trade['source']}"],
                    textposition="top center",
                    name=f"{trade['source']} Trade",
                    showlegend=False
                ),
                row=1, col=1
            )

    # Volume bars
    colors = ['#00ff88' if close >= open else '#ff4444'
              for close, open in zip(data['close'], data['open'])]

    fig.add_trace(
        go.Bar(
            x=data.index,
            y=data['volume'],
            marker_color=colors,
            name="Volume",
            opacity=0.7
        ),
        row=2, col=1
    )

    # Add TP/SL position boxes (drawing tools)
    if tp_sl_boxes:
        for box in tp_sl_boxes:
            # TP Box (green)
            if box['type'] == 'tp':
                fig.add_shape(
                    type="rect",
                    x0=box['start'], x1=box['end'],
                    y0=box['price'], y1=box['price'] + box.get('height', 50),
                    fillcolor="rgba(0, 255, 0, 0.3)",
                    line=dict(color="#00ff00", width=2),
                    row=1, col=1
                )
                # TP Label
                fig.add_annotation(
                    x=box['start'], y=box['price'] + box.get('height', 50),
                    text=f"TP: ${box['price']:.2f}",
                    showarrow=False,
                    bgcolor="#00ff00",
                    font=dict(color="black", size=10),
                    row=1, col=1
                )
            # SL Box (red)
            elif box['type'] == 'sl':
                fig.add_shape(
                    type="rect",
                    x0=box['start'], x1=box['end'],
                    y0=box['price'], y1=box['price'] - box.get('height', 50),
                    fillcolor="rgba(255, 0, 0, 0.3)",
                    line=dict(color="#ff0000", width=2),
                    row=1, col=1
                )
                # SL Label
                fig.add_annotation(
                    x=box['start'], y=box['price'] - box.get('height', 50),
                    text=f"SL: ${box['price']:.2f}",
                    showarrow=False,
                    bgcolor="#ff0000",
                    font=dict(color="white", size=10),
                    row=1, col=1
                )

    # TradingView-style layout
    fig.update_layout(
        title=None,  # No title for cleaner look
        xaxis_rangeslider_visible=False,
        height=700,
        showlegend=False,  # Cleaner like TradingView
        plot_bgcolor='#131722',  # TradingView dark theme
        paper_bgcolor='#131722',
        font=dict(color='#d1d4dc', family="Arial"),
        margin=dict(l=0, r=0, t=30, b=0),
        dragmode='pan'  # Enable panning like TradingView
    )

    # TradingView-style axes
    fig.update_xaxes(
        gridcolor='#2a2e39',
        showgrid=True,
        zeroline=False,
        showline=True,
        linecolor='#2a2e39',
        tickcolor='#2a2e39',
        tickfont=dict(color='#787b86', size=11),
        showticklabels=True
    )
    fig.update_yaxes(
        gridcolor='#2a2e39',
        showgrid=True,
        zeroline=False,
        showline=True,
        linecolor='#2a2e39',
        tickcolor='#2a2e39',
        tickfont=dict(color='#787b86', size=11),
        side='right',  # Price on right like TradingView
        showticklabels=True
    )

    # Volume chart styling
    fig.update_yaxes(
        showticklabels=False,
        row=2, col=1
    )

    return fig


def init_trading_system(symbol: str):
    """Initialize the trading environment and agent"""

    # Create sample data
    data = create_sample_data(symbol, periods=1000, freq='5min')

    # Setup environment
    env = InteractiveTradingEnv(
        df=data,
        initial_cash=50000,
        transaction_cost=0.5,  # $0.5 per NQ contract
        enable_patterns=True
    )

    # Create agent
    agent = create_trading_agent(env)

    return env, agent, data


def main():
    st.title("🎮 Trackmania-Style RL Trading")
    st.markdown("**Interactive Human vs AI Trading auf NQ (Nasdaq)**")

    # Sidebar controls
    st.sidebar.header("🎯 Controls")

    # Initialize system
    if st.sidebar.button("🚀 Start Trading Session", key="init"):
        with st.spinner("Initializing trading system..."):
            env, agent, data = init_trading_system("NQ")
            st.session_state.env = env
            st.session_state.agent = agent
            st.session_state.data = data
            st.session_state.current_step = 50  # Start at step 50
        st.success("Trading system ready!")

    if st.session_state.env is None:
        st.info("👆 Click 'Start Trading Session' to begin")
        return

    # Current market info
    col1, col2, col3, col4 = st.columns(4)

    current_price = st.session_state.data.iloc[st.session_state.current_step]['close']
    portfolio_value = st.session_state.env.cash + (st.session_state.env.shares_held * current_price)

    with col1:
        st.metric("💰 NQ Price", f"${current_price:.2f}")
    with col2:
        st.metric("💵 Portfolio", f"${portfolio_value:.2f}")
    with col3:
        st.metric("📊 Position", st.session_state.env.shares_held)
    with col4:
        st.metric("📈 PnL", f"${portfolio_value - 50000:.2f}")

    # Main trading interface
    col_left, col_right = st.columns([3, 1])

    with col_left:
        # Generate patterns for current view
        pattern_manager = PatternManager()
        current_data_slice = st.session_state.data.iloc[max(0, st.session_state.current_step-100):st.session_state.current_step+1]

        # Detect patterns
        signals = pattern_manager.get_trading_signals(current_data_slice, st.session_state.current_step)

        # Mock pattern data for visualization
        patterns = {}
        if signals.get('in_fvg_zone'):
            patterns['fvg_zones'] = [{
                'start': st.session_state.current_step - 10,
                'end': st.session_state.current_step + 5,
                'low': current_price - 50,
                'high': current_price + 50
            }]

        if signals.get('in_order_block'):
            patterns['order_blocks'] = [{
                'start': st.session_state.current_step - 20,
                'end': st.session_state.current_step,
                'low': current_price - 100,
                'high': current_price - 50
            }]

        # Combine all trades for visualization
        all_trades = st.session_state.human_trades + st.session_state.ai_trades

        # Create and display chart
        fig = create_candlestick_chart(current_data_slice, patterns, all_trades, st.session_state.tp_sl_boxes)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("🎮 Trading Controls")

        # Human trading section
        st.markdown("**👤 Your Actions:**")
        col_buy, col_sell = st.columns(2)

        with col_buy:
            if st.button("🟢 BUY", key="human_buy", help="Buy NQ contract"):
                # Execute human buy
                trade = {
                    'timestamp': st.session_state.current_step,
                    'price': current_price,
                    'type': 'buy',
                    'source': 'Human'
                }
                st.session_state.human_trades.append(trade)
                st.success(f"✅ Bought at ${current_price:.2f}")

        with col_sell:
            if st.button("🔴 SELL", key="human_sell", help="Sell NQ contract"):
                # Execute human sell
                trade = {
                    'timestamp': st.session_state.current_step,
                    'price': current_price,
                    'type': 'sell',
                    'source': 'Human'
                }
                st.session_state.human_trades.append(trade)
                st.success(f"✅ Sold at ${current_price:.2f}")

        # Drawing Tools Section
        st.markdown("**🛠️ Drawing Tools:**")

        # TP/SL Tools Toggle
        st.session_state.show_tp_sl_tools = st.checkbox(
            "📊 TP/SL Tools",
            value=st.session_state.show_tp_sl_tools,
            key="tp_sl_toggle"
        )

        if st.session_state.show_tp_sl_tools:
            col_tp, col_sl = st.columns(2)

            with col_tp:
                if st.button("🟢 Add TP", key="add_tp", help="Add Take Profit level"):
                    tp_box = {
                        'type': 'tp',
                        'price': current_price + 100,  # 100 points above
                        'start': st.session_state.current_step,
                        'end': st.session_state.current_step + 20,
                        'height': 50
                    }
                    st.session_state.tp_sl_boxes.append(tp_box)
                    st.success(f"TP added at ${tp_box['price']:.2f}")

            with col_sl:
                if st.button("🔴 Add SL", key="add_sl", help="Add Stop Loss level"):
                    sl_box = {
                        'type': 'sl',
                        'price': current_price - 100,  # 100 points below
                        'start': st.session_state.current_step,
                        'end': st.session_state.current_step + 20,
                        'height': 50
                    }
                    st.session_state.tp_sl_boxes.append(sl_box)
                    st.error(f"SL added at ${sl_box['price']:.2f}")

            # Clear all TP/SL
            if st.button("🗑️ Clear All", key="clear_tp_sl"):
                st.session_state.tp_sl_boxes = []
                st.info("All TP/SL levels cleared")

        # AI trading section
        st.markdown("**🤖 AI Actions:**")

        # Continuous AI Trading Toggle
        ai_was_active = st.session_state.ai_trading_active
        st.session_state.ai_trading_active = st.checkbox(
            "🚀 Continuous AI Trading",
            value=st.session_state.ai_trading_active,
            key="ai_continuous",
            help="AI will trade automatically until you stop it"
        )

        # Manual AI Trade Button
        if not st.session_state.ai_trading_active:
            if st.button("🎯 Let AI Trade Once", key="ai_trade_once"):
                # Get AI action
                obs = st.session_state.env._get_observation()
                action, _states = st.session_state.agent.model.predict(obs)

                if action == 1:  # Buy
                    trade = {
                        'timestamp': st.session_state.current_step,
                        'price': current_price,
                        'type': 'buy',
                        'source': 'AI'
                    }
                    st.session_state.ai_trades.append(trade)
                    st.info(f"🤖 AI Bought at ${current_price:.2f}")
                elif action == 2:  # Sell
                    trade = {
                        'timestamp': st.session_state.current_step,
                        'price': current_price,
                        'type': 'sell',
                        'source': 'AI'
                    }
                    st.session_state.ai_trades.append(trade)
                    st.info(f"🤖 AI Sold at ${current_price:.2f}")
                else:
                    st.info("🤖 AI chose to HOLD")

        # Pattern signals
        st.markdown("**📊 Current Signals:**")
        if signals.get('in_fvg_zone'):
            st.success("🎯 In FVG Zone")
        if signals.get('in_order_block'):
            st.info("📦 In Order Block")
        if signals.get('bullish_structure'):
            st.success("📈 Bullish Structure")
        if signals.get('bearish_structure'):
            st.error("📉 Bearish Structure")

        # Feedback section
        st.markdown("**💭 Feedback for AI:**")
        feedback = st.radio(
            "Rate AI's recent performance:",
            ["👍 Good", "👎 Bad", "😐 Neutral"],
            key="feedback_radio"
        )

        if st.button("📝 Submit Feedback", key="submit_feedback"):
            feedback_value = {"👍 Good": 1, "👎 Bad": -1, "😐 Neutral": 0}[feedback]
            st.session_state.feedback_history.append({
                'step': st.session_state.current_step,
                'feedback': feedback_value,
                'timestamp': time.time()
            })
            st.success("Feedback recorded! AI will learn from this.")

        # Next step
        if st.button("⏭️ Next Step", key="next_step"):
            st.session_state.current_step = min(
                st.session_state.current_step + 1,
                len(st.session_state.data) - 1
            )
            st.rerun()

        # Auto-play mode
        auto_play = st.checkbox("🎬 Auto-play", key="auto_play")
        if auto_play:
            time.sleep(0.5)
            st.session_state.current_step = min(
                st.session_state.current_step + 1,
                len(st.session_state.data) - 1
            )
            st.rerun()

    # Performance summary
    st.subheader("📈 Performance Comparison")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("👤 Human Trades", len(st.session_state.human_trades))

    with col2:
        st.metric("🤖 AI Trades", len(st.session_state.ai_trades))

    with col3:
        st.metric("💭 Feedback Given", len(st.session_state.feedback_history))

    # Trade history
    if st.session_state.human_trades or st.session_state.ai_trades:
        st.subheader("📋 Recent Trades")

        all_trades_df = pd.DataFrame(st.session_state.human_trades + st.session_state.ai_trades)
        if not all_trades_df.empty:
            all_trades_df = all_trades_df.sort_values('timestamp', ascending=False)
            st.dataframe(
                all_trades_df[['source', 'type', 'price', 'timestamp']].head(10),
                use_container_width=True
            )


if __name__ == "__main__":
    main()