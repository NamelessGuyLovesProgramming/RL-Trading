"""
TradingView-Style Chart mit In-Chart Controls und Mouse Zoom
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
    page_title="RL Trading - TradingView Native",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
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
if 'selected_timeframe' not in st.session_state:
    st.session_state.selected_timeframe = '5m'
if 'selected_indicators' not in st.session_state:
    st.session_state.selected_indicators = ['MA20']
if 'zoom_level' not in st.session_state:
    st.session_state.zoom_level = 100  # Default: 100 candles visible
if 'chart_focus' not in st.session_state:
    st.session_state.chart_focus = 'latest'  # Focus on latest candle


def create_tradingview_chart(data: pd.DataFrame, current_step: int, timeframe: str = '5m',
                           patterns: dict = None, trades: list = None, tp_sl_boxes: list = None,
                           indicators: list = None, zoom_level: int = 100):
    """Create TradingView-native style chart with in-chart controls and zoom"""

    # Calculate visible range based on zoom
    if st.session_state.chart_focus == 'latest':
        view_end = min(len(data) - 1, current_step + 10)
        view_start = max(0, view_end - zoom_level)
    else:
        view_start = max(0, current_step - zoom_level//2)
        view_end = min(len(data) - 1, current_step + zoom_level//2)

    # Slice data to visible range
    visible_data = data.iloc[view_start:view_end+1].reset_index(drop=True)
    candle_numbers = list(range(len(visible_data)))

    # Create main chart
    fig = make_subplots(
        rows=1, cols=1,
        subplot_titles=None
    )

    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=candle_numbers,
            open=visible_data['open'],
            high=visible_data['high'],
            low=visible_data['low'],
            close=visible_data['close'],
            name="NQ",
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350',
            showlegend=False
        )
    )

    # Add indicators
    if indicators:
        if 'MA20' in indicators:
            ma_period = min(20, len(visible_data))
            if ma_period > 1:
                ma_values = visible_data['close'].rolling(window=ma_period).mean()
                fig.add_trace(
                    go.Scatter(
                        x=candle_numbers,
                        y=ma_values,
                        mode='lines',
                        name='MA20',
                        line=dict(color='#ffeb3b', width=2),
                        showlegend=False
                    )
                )

        if 'Bollinger' in indicators:
            bb_period = min(20, len(visible_data))
            if bb_period > 1:
                ma = visible_data['close'].rolling(window=bb_period).mean()
                std = visible_data['close'].rolling(window=bb_period).std()
                upper_band = ma + (std * 2)
                lower_band = ma - (std * 2)

                fig.add_trace(
                    go.Scatter(
                        x=candle_numbers, y=upper_band,
                        mode='lines', name='BB Upper',
                        line=dict(color='#9c27b0', width=1, dash='dot'),
                        showlegend=False
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=candle_numbers, y=lower_band,
                        mode='lines', name='BB Lower',
                        line=dict(color='#9c27b0', width=1, dash='dot'),
                        showlegend=False,
                        fill='tonexty',
                        fillcolor='rgba(156, 39, 176, 0.1)'
                    )
                )

    # Add trades
    if trades:
        for trade in trades:
            if view_start <= trade['timestamp'] <= view_end:
                relative_pos = trade['timestamp'] - view_start
                if relative_pos < len(candle_numbers):
                    color = '#26a69a' if trade['type'] == 'buy' else '#ef5350'
                    symbol = 'triangle-up' if trade['type'] == 'buy' else 'triangle-down'

                    fig.add_trace(
                        go.Scatter(
                            x=[relative_pos],
                            y=[trade['price']],
                            mode='markers+text',
                            marker=dict(size=12, color=color, symbol=symbol),
                            text=[trade['source'][:3]],
                            textposition="top center" if trade['type'] == 'buy' else "bottom center",
                            showlegend=False
                        )
                    )

    # Add TP/SL boxes
    if tp_sl_boxes:
        for box in tp_sl_boxes:
            if view_start <= box['start'] <= view_end:
                rel_start = max(0, box['start'] - view_start)
                rel_end = min(len(candle_numbers) - 1, box['end'] - view_start)

                if box['type'] == 'tp':
                    fig.add_shape(
                        type="rect",
                        x0=rel_start, x1=rel_end,
                        y0=box['price'], y1=box['price'] + box.get('height', 50),
                        fillcolor="rgba(0, 255, 0, 0.2)",
                        line=dict(color="#00ff00", width=2)
                    )
                elif box['type'] == 'sl':
                    fig.add_shape(
                        type="rect",
                        x0=rel_start, x1=rel_end,
                        y0=box['price'], y1=box['price'] - box.get('height', 50),
                        fillcolor="rgba(255, 0, 0, 0.2)",
                        line=dict(color="#ff0000", width=2)
                    )

    # TradingView-style layout with full-screen chart
    fig.update_layout(
        title=None,
        xaxis_rangeslider_visible=False,
        height=800,  # Taller chart
        showlegend=False,
        plot_bgcolor='#131722',
        paper_bgcolor='#131722',
        font=dict(color='#d1d4dc', family="Arial, sans-serif"),
        margin=dict(l=0, r=0, t=0, b=0),  # No margins for full-screen effect
        dragmode='pan',
        xaxis=dict(
            showgrid=True,
            gridcolor='#2a2e39',
            zeroline=False,
            showline=False,
            showticklabels=True,
            tickfont=dict(color='#787b86', size=10),
            fixedrange=False  # Enable mouse wheel zoom
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#2a2e39',
            zeroline=False,
            showline=False,
            side='right',
            showticklabels=True,
            tickfont=dict(color='#787b86', size=10),
            fixedrange=False  # Enable mouse wheel zoom
        )
    )

    # Add annotations for in-chart UI elements
    current_price = visible_data['close'].iloc[-1] if len(visible_data) > 0 else 0

    # Top-left: Timeframe selector overlay
    timeframes_text = f"📅 {timeframe.upper()}"
    fig.add_annotation(
        x=0.02, y=0.98,
        xref="paper", yref="paper",
        text=timeframes_text,
        showarrow=False,
        bgcolor="rgba(0, 0, 0, 0.7)",
        bordercolor="#2a2e39",
        borderwidth=1,
        font=dict(color="#d1d4dc", size=12),
        xanchor="left", yanchor="top"
    )

    # Top-right: Current price
    price_text = f"💰 ${current_price:.2f}"
    fig.add_annotation(
        x=0.98, y=0.98,
        xref="paper", yref="paper",
        text=price_text,
        showarrow=False,
        bgcolor="rgba(0, 0, 0, 0.7)",
        bordercolor="#2a2e39",
        borderwidth=1,
        font=dict(color="#26a69a", size=12, weight="bold"),
        xanchor="right", yanchor="top"
    )

    # Bottom-left: Indicators
    if indicators:
        indicators_text = "📊 " + " • ".join(indicators)
        fig.add_annotation(
            x=0.02, y=0.02,
            xref="paper", yref="paper",
            text=indicators_text,
            showarrow=False,
            bgcolor="rgba(0, 0, 0, 0.7)",
            bordercolor="#2a2e39",
            borderwidth=1,
            font=dict(color="#ffeb3b", size=10),
            xanchor="left", yanchor="bottom"
        )

    # Bottom-right: Zoom info
    zoom_text = f"🔍 {zoom_level} bars | Focus: {st.session_state.chart_focus}"
    fig.add_annotation(
        x=0.98, y=0.02,
        xref="paper", yref="paper",
        text=zoom_text,
        showarrow=False,
        bgcolor="rgba(0, 0, 0, 0.7)",
        bordercolor="#2a2e39",
        borderwidth=1,
        font=dict(color="#787b86", size=10),
        xanchor="right", yanchor="bottom"
    )

    # Add drawing tools overlay (left side)
    tools_text = "🛠️ Tools:\\n📏 Line\\n📐 Rect\\n🟢 TP\\n🔴 SL"
    fig.add_annotation(
        x=0.02, y=0.5,
        xref="paper", yref="paper",
        text=tools_text,
        showarrow=False,
        bgcolor="rgba(0, 0, 0, 0.8)",
        bordercolor="#2a2e39",
        borderwidth=1,
        font=dict(color="#d1d4dc", size=9),
        xanchor="left", yanchor="middle"
    )

    return fig


def init_trading_system(symbol: str):
    """Initialize the trading environment and agent"""
    data = create_sample_data(symbol, periods=1000, freq='5min')

    env = InteractiveTradingEnv(
        df=data,
        initial_cash=50000,
        transaction_cost=0.5,
        enable_patterns=True
    )

    agent = create_trading_agent(env)
    return env, agent, data


def handle_zoom(direction: str):
    """Handle zoom in/out functionality"""
    if direction == "in":
        # Zoom in: Show fewer candles, focus on latest
        st.session_state.zoom_level = max(20, st.session_state.zoom_level - 20)
        st.session_state.chart_focus = 'latest'
    elif direction == "out":
        # Zoom out: Show more candles
        st.session_state.zoom_level = min(500, st.session_state.zoom_level + 30)

    st.rerun()


def main():
    st.markdown("""
    <style>
    .main > div {
        padding: 0rem;
    }
    .stPlotlyChart {
        height: 100vh !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Minimal header
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])

    with col1:
        st.markdown("**📈 RL Trading - TradingView Native**")

    with col2:
        if st.button("🚀 Init", help="Initialize trading system"):
            with st.spinner("Loading..."):
                env, agent, data = init_trading_system("NQ")
                st.session_state.env = env
                st.session_state.agent = agent
                st.session_state.data = data
                st.session_state.current_step = 50
            st.success("Ready!")

    with col3:
        if st.button("🔍+", help="Zoom In (Mouse wheel up)"):
            handle_zoom("in")

    with col4:
        if st.button("🔍-", help="Zoom Out (Mouse wheel down)"):
            handle_zoom("out")

    with col5:
        if st.button("⏭️", help="Next candle"):
            if st.session_state.data is not None:
                if st.session_state.current_step < len(st.session_state.data) - 1:
                    st.session_state.current_step += 1
                    st.rerun()

    if st.session_state.env is None:
        st.info("👆 Click 'Init' to start the TradingView-style interface")
        return

    # Main TradingView-style chart (full screen)
    current_price = st.session_state.data.iloc[st.session_state.current_step]['close']

    # Generate patterns
    pattern_manager = PatternManager()
    current_data_slice = st.session_state.data.iloc[max(0, st.session_state.current_step-200):st.session_state.current_step+50]
    signals = pattern_manager.get_trading_signals(current_data_slice, st.session_state.current_step)

    # Mock pattern data
    patterns = {}
    if signals.get('in_fvg_zone'):
        patterns['fvg_zones'] = [{
            'start': st.session_state.current_step - 10,
            'end': st.session_state.current_step + 5,
            'low': current_price - 50,
            'high': current_price + 50
        }]

    # Combine trades
    all_trades = st.session_state.human_trades + st.session_state.ai_trades

    # Create and display full-screen TradingView chart
    fig = create_tradingview_chart(
        st.session_state.data,
        st.session_state.current_step,
        st.session_state.selected_timeframe,
        patterns,
        all_trades,
        st.session_state.tp_sl_boxes,
        st.session_state.selected_indicators,
        st.session_state.zoom_level
    )

    # Full-screen chart with custom config for zoom
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            'displayModeBar': False,  # Hide toolbar for cleaner look
            'scrollZoom': True,       # Enable mouse wheel zoom
            'doubleClick': 'reset',   # Double-click to reset zoom
            'showTips': False,
            'displaylogo': False
        }
    )

    # Bottom controls (minimal)
    st.markdown("---")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        if st.button("🟢 BUY"):
            trade = {
                'timestamp': st.session_state.current_step,
                'price': current_price,
                'type': 'buy',
                'source': 'Human'
            }
            st.session_state.human_trades.append(trade)
            st.success(f"Buy ${current_price:.2f}")

    with col2:
        if st.button("🔴 SELL"):
            trade = {
                'timestamp': st.session_state.current_step,
                'price': current_price,
                'type': 'sell',
                'source': 'Human'
            }
            st.session_state.human_trades.append(trade)
            st.success(f"Sell ${current_price:.2f}")

    with col3:
        if st.button("🎯 AI Trade"):
            obs = st.session_state.env._get_observation()
            action, _states = st.session_state.agent.model.predict(obs)

            if action == 1:
                trade = {
                    'timestamp': st.session_state.current_step,
                    'price': current_price,
                    'type': 'buy',
                    'source': 'AI'
                }
                st.session_state.ai_trades.append(trade)
                st.info(f"AI Buy ${current_price:.2f}")
            elif action == 2:
                trade = {
                    'timestamp': st.session_state.current_step,
                    'price': current_price,
                    'type': 'sell',
                    'source': 'AI'
                }
                st.session_state.ai_trades.append(trade)
                st.info(f"AI Sell ${current_price:.2f}")

    with col4:
        if st.button("🟢 Add TP"):
            tp_box = {
                'type': 'tp',
                'price': current_price + 100,
                'start': st.session_state.current_step,
                'end': st.session_state.current_step + 20,
                'height': 50
            }
            st.session_state.tp_sl_boxes.append(tp_box)
            st.success(f"TP ${tp_box['price']:.2f}")

    with col5:
        if st.button("🔴 Add SL"):
            sl_box = {
                'type': 'sl',
                'price': current_price - 100,
                'start': st.session_state.current_step,
                'end': st.session_state.current_step + 20,
                'height': 50
            }
            st.session_state.tp_sl_boxes.append(sl_box)
            st.error(f"SL ${sl_box['price']:.2f}")

    with col6:
        if st.button("🗑️ Clear"):
            st.session_state.tp_sl_boxes = []
            st.info("Cleared")

    # Status info (compact)
    portfolio_value = st.session_state.env.cash + (st.session_state.env.shares_held * current_price)
    st.markdown(f"**💰 ${current_price:.2f} | 💵 ${portfolio_value:.2f} | 📊 {st.session_state.env.shares_held} | 🎯 Step {st.session_state.current_step} | 🔍 {st.session_state.zoom_level} bars**")

    # Instructions
    st.markdown("""
    **🖱️ Mouse Controls:**
    - **Wheel Up**: Zoom In (fewer candles, larger view)
    - **Wheel Down**: Zoom Out (more candles, smaller view)
    - **Pan**: Drag to move chart
    - **Double-Click**: Reset zoom

    **Chart UI:** All controls are overlaid ON the chart like TradingView!
    """)


if __name__ == "__main__":
    main()