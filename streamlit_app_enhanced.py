"""
Enhanced TradingView-Style Interactive RL Trading Dashboard
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
from datetime import datetime, time as dt_time

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from env import InteractiveTradingEnv
from agent import TradingPPOAgent, create_trading_agent
from data_feed import TradingDataManager, create_sample_data
from patterns import PatternManager

st.set_page_config(
    page_title="RL Trading - TradingView Style",
    page_icon="📈",
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
if 'selected_timeframe' not in st.session_state:
    st.session_state.selected_timeframe = '5m'
if 'selected_indicators' not in st.session_state:
    st.session_state.selected_indicators = []
if 'active_drawing_tool' not in st.session_state:
    st.session_state.active_drawing_tool = None


def add_session_indicators(fig, data, candle_numbers):
    """Add trading session indicators (NY, London, Asia)"""

    # Session times (simplified - just visual indicators)
    sessions = [
        {'name': 'Asia', 'start_hour': 0, 'end_hour': 8, 'color': '#ffeb3b'},
        {'name': 'London', 'start_hour': 8, 'end_hour': 16, 'color': '#2196f3'},
        {'name': 'NY', 'start_hour': 16, 'end_hour': 24, 'color': '#f44336'}
    ]

    # Add session background colors
    for i in range(0, len(data), 24):  # Every 24 steps = 1 day (assuming 1h candles)
        for session in sessions:
            start_idx = i + session['start_hour']
            end_idx = min(i + session['end_hour'], len(data) - 1)

            if start_idx < len(data):
                fig.add_vrect(
                    x0=start_idx, x1=end_idx,
                    fillcolor=session['color'],
                    opacity=0.08,
                    line_width=0,
                    row=1, col=1
                )

                # Add session label
                if start_idx + 4 < len(data):
                    fig.add_annotation(
                        x=start_idx + 2,
                        y=data.iloc[start_idx:end_idx]['high'].max() if end_idx > start_idx else data.iloc[start_idx]['high'],
                        text=session['name'],
                        showarrow=False,
                        font=dict(color=session['color'], size=9),
                        bgcolor="rgba(0,0,0,0.6)",
                        row=1, col=1
                    )

    return fig


def create_candlestick_chart(data: pd.DataFrame, current_step: int, timeframe: str = '5m', patterns: dict = None, trades: list = None, tp_sl_boxes: list = None, indicators: list = None):
    """Create TradingView-style interactive candlestick chart with timeframe support"""

    # Create proper x-axis labels (sequential candle numbers)
    data_indexed = data.reset_index(drop=True)
    candle_numbers = list(range(len(data_indexed)))

    # Generate time labels based on timeframe
    time_labels = []
    for i in range(len(data_indexed)):
        if timeframe == '1m':
            time_labels.append(f"{i:02d}:00")
        elif timeframe == '5m':
            time_labels.append(f"{(i*5)//60:02d}:{(i*5)%60:02d}")
        elif timeframe == '15m':
            time_labels.append(f"{(i*15)//60:02d}:{(i*15)%60:02d}")
        elif timeframe == '30m':
            time_labels.append(f"{(i*30)//60:02d}:{(i*30)%60:02d}")
        elif timeframe == '1h':
            time_labels.append(f"{i:02d}:00")
        elif timeframe == '4h':
            time_labels.append(f"{(i*4)%24:02d}:00")
        else:
            time_labels.append(f"{i}")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.8, 0.2],
        subplot_titles=None
    )

    # TradingView-style candlesticks with proper x-axis
    fig.add_trace(
        go.Candlestick(
            x=candle_numbers,
            open=data_indexed['open'],
            high=data_indexed['high'],
            low=data_indexed['low'],
            close=data_indexed['close'],
            name="NQ",
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
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
            color = '#26a69a' if trade['type'] == 'buy' else '#ef5350'
            symbol = 'triangle-up' if trade['type'] == 'buy' else 'triangle-down'

            fig.add_trace(
                go.Scatter(
                    x=[trade['timestamp']],
                    y=[trade['price']],
                    mode='markers+text',
                    marker=dict(
                        size=12,
                        color=color,
                        symbol=symbol,
                        line=dict(width=1, color='white')
                    ),
                    text=[f"{trade['source'][:3]}"],
                    textposition="middle center",
                    name=f"{trade['source']} Trade",
                    showlegend=False
                ),
                row=1, col=1
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

    # Volume bars with proper x-axis
    colors = ['#26a69a' if close >= open else '#ef5350'
              for close, open in zip(data_indexed['close'], data_indexed['open'])]

    fig.add_trace(
        go.Bar(
            x=candle_numbers,
            y=data_indexed['volume'],
            marker_color=colors,
            name="Volume",
            opacity=0.6,
            showlegend=False
        ),
        row=2, col=1
    )

    # Add session indicators
    # Session indicators will be added at the end of the function

    # Set proper view range - show only recent candles around current step
    view_start = max(0, current_step - 50)  # Show 50 candles before current
    view_end = min(len(data_indexed) - 1, current_step + 10)  # Show 10 candles ahead

    # TradingView-style layout with proper range
    fig.update_layout(
        title=None,
        xaxis_rangeslider_visible=False,
        height=700,
        showlegend=False,
        plot_bgcolor='#131722',
        paper_bgcolor='#131722',
        font=dict(color='#d1d4dc', family="Arial"),
        margin=dict(l=0, r=0, t=30, b=0),
        dragmode='pan',
        xaxis=dict(
            range=[view_start, view_end],  # Focus on current area
            fixedrange=False
        ),
        yaxis=dict(
            autorange=True,  # Auto-scale Y-axis to visible data
            fixedrange=False
        )
    )

    # Add selected indicators
    if indicators:
        for indicator in indicators:
            if indicator == 'MA20':
                # Simple Moving Average (mock)
                ma_values = data_indexed['close'].rolling(window=min(20, len(data_indexed))).mean()
                fig.add_trace(
                    go.Scatter(
                        x=candle_numbers,
                        y=ma_values,
                        mode='lines',
                        name='MA20',
                        line=dict(color='#ffeb3b', width=2),
                        showlegend=False
                    ),
                    row=1, col=1
                )
            elif indicator == 'Bollinger':
                # Bollinger Bands (mock)
                ma = data_indexed['close'].rolling(window=min(20, len(data_indexed))).mean()
                std = data_indexed['close'].rolling(window=min(20, len(data_indexed))).std()
                upper_band = ma + (std * 2)
                lower_band = ma - (std * 2)

                fig.add_trace(
                    go.Scatter(
                        x=candle_numbers,
                        y=upper_band,
                        mode='lines',
                        name='BB Upper',
                        line=dict(color='#9c27b0', width=1),
                        showlegend=False
                    ),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(
                        x=candle_numbers,
                        y=lower_band,
                        mode='lines',
                        name='BB Lower',
                        line=dict(color='#9c27b0', width=1),
                        showlegend=False
                    ),
                    row=1, col=1
                )
            elif indicator == 'RSI':
                # RSI would go in a separate subplot in real implementation
                # For now, just show as overlay (mock)
                rsi_values = [50 + (i % 20 - 10) for i in range(len(data_indexed))]  # Mock RSI
                fig.add_trace(
                    go.Scatter(
                        x=candle_numbers,
                        y=[data_indexed['close'].iloc[i] + rsi_values[i] for i in range(len(data_indexed))],
                        mode='lines',
                        name='RSI',
                        line=dict(color='#ff5722', width=1),
                        showlegend=False,
                        visible='legendonly'
                    ),
                    row=1, col=1
                )

    # TradingView-style axes with time labels
    fig.update_xaxes(
        gridcolor='#2a2e39',
        showgrid=True,
        zeroline=False,
        showline=True,
        linecolor='#2a2e39',
        tickcolor='#2a2e39',
        tickfont=dict(color='#787b86', size=11),
        showticklabels=True,
        ticktext=time_labels[::max(1, len(time_labels)//10)],  # Show every 10th label
        tickvals=candle_numbers[::max(1, len(candle_numbers)//10)]
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

    # Add session indicators with proper mapping
    fig = add_session_indicators(fig, data_indexed, candle_numbers)

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


def execute_ai_trade(current_price, current_step):
    """Execute AI trade and return trade info"""
    obs = st.session_state.env._get_observation()
    action, _states = st.session_state.agent.model.predict(obs)

    if action == 1:  # Buy
        trade = {
            'timestamp': current_step,
            'price': current_price,
            'type': 'buy',
            'source': 'AI-Auto' if st.session_state.ai_trading_active else 'AI'
        }
        st.session_state.ai_trades.append(trade)
        return trade, "bought"
    elif action == 2:  # Sell
        trade = {
            'timestamp': current_step,
            'price': current_price,
            'type': 'sell',
            'source': 'AI-Auto' if st.session_state.ai_trading_active else 'AI'
        }
        st.session_state.ai_trades.append(trade)
        return trade, "sold"
    else:
        return None, "hold"


def main():
    st.title("📈 TradingView-Style RL Trading")
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

    # TradingView-style toolbar above chart
    st.markdown("---")

    # Timeframe selection (above chart)
    col_tf1, col_tf2, col_tf3, col_tf4 = st.columns(4)
    with col_tf1:
        st.markdown("**⏱️ Timeframes:**")

    timeframes = ['1m', '5m', '15m', '30m', '1h', '4h']
    tf_cols = st.columns(len(timeframes))

    for i, tf in enumerate(timeframes):
        with tf_cols[i]:
            if st.button(tf, key=f"tf_{tf}",
                        help=f"Switch to {tf} timeframe",
                        type="primary" if st.session_state.selected_timeframe == tf else "secondary"):
                st.session_state.selected_timeframe = tf
                st.rerun()

    # Indicators selection (next to timeframes)
    st.markdown("**📊 Indicators:**")
    available_indicators = ['MA20', 'Bollinger', 'RSI', 'MACD', 'Volume Profile', 'Fibonacci']

    # Create indicator buttons in columns
    ind_cols = st.columns(len(available_indicators))
    for i, indicator in enumerate(available_indicators):
        with ind_cols[i]:
            if st.checkbox(indicator,
                          key=f"ind_{indicator}",
                          value=indicator in st.session_state.selected_indicators):
                if indicator not in st.session_state.selected_indicators:
                    st.session_state.selected_indicators.append(indicator)
            else:
                if indicator in st.session_state.selected_indicators:
                    st.session_state.selected_indicators.remove(indicator)

    st.markdown("---")

    # Main trading interface with drawing tools sidebar
    col_tools, col_chart, col_controls = st.columns([1, 4, 1])

    # Left sidebar - Drawing Tools
    with col_tools:
        st.markdown("**🛠️ Drawing Tools**")

        # Drawing tool buttons
        tools = [
            ('📏', 'Trend Line', 'trendline'),
            ('📐', 'Rectangle', 'rectangle'),
            ('🟢', 'TP Box', 'tp_box'),
            ('🔴', 'SL Box', 'sl_box'),
            ('📊', 'Fib Retracement', 'fibonacci'),
            ('📍', 'Support/Resistance', 'support_resistance'),
            ('🎯', 'Target', 'target'),
            ('🗑️', 'Clear All', 'clear')
        ]

        for emoji, name, tool_id in tools:
            if tool_id == 'clear':
                if st.button(f"{emoji} {name}", key=f"tool_{tool_id}", help=f"Clear all drawings"):
                    st.session_state.tp_sl_boxes = []
                    st.success("All drawings cleared")
            else:
                button_type = "primary" if st.session_state.active_drawing_tool == tool_id else "secondary"
                if st.button(f"{emoji} {name}", key=f"tool_{tool_id}",
                           help=f"Activate {name} drawing tool",
                           type=button_type):
                    st.session_state.active_drawing_tool = tool_id
                    if tool_id == 'tp_box':
                        # Add TP box at current price
                        tp_box = {
                            'type': 'tp',
                            'price': current_price + 100,
                            'start': st.session_state.current_step,
                            'end': st.session_state.current_step + 20,
                            'height': 50
                        }
                        st.session_state.tp_sl_boxes.append(tp_box)
                        st.success(f"TP added at ${tp_box['price']:.2f}")
                    elif tool_id == 'sl_box':
                        # Add SL box at current price
                        sl_box = {
                            'type': 'sl',
                            'price': current_price - 100,
                            'start': st.session_state.current_step,
                            'end': st.session_state.current_step + 20,
                            'height': 50
                        }
                        st.session_state.tp_sl_boxes.append(sl_box)
                        st.error(f"SL added at ${sl_box['price']:.2f}")

        st.markdown("---")
        st.markdown(f"**Active Tool:** {st.session_state.active_drawing_tool or 'None'}")
        st.markdown(f"**Timeframe:** {st.session_state.selected_timeframe}")
        st.markdown(f"**Indicators:** {len(st.session_state.selected_indicators)}")

    # Center - Chart
    with col_chart:
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

        # Create and display chart with all enhancements
        fig = create_candlestick_chart(
            current_data_slice,
            st.session_state.current_step - max(0, st.session_state.current_step-100),  # Relative position in slice
            st.session_state.selected_timeframe,
            patterns,
            all_trades,
            st.session_state.tp_sl_boxes,
            st.session_state.selected_indicators
        )
        st.plotly_chart(fig, use_container_width=True, key="main_chart")

    # Right sidebar - Trading Controls
    with col_controls:
        st.markdown("**🎮 Trading Controls**")

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

        # Quick Actions
        st.markdown("**⚡ Quick Actions:**")

        if st.button("🔄 Reset Chart", help="Reset chart view"):
            st.session_state.current_step = 50
            st.rerun()

        if st.button("💾 Save Setup", help="Save current configuration"):
            st.info("Setup saved! (mock)")

        if st.button("📄 Load Setup", help="Load saved configuration"):
            st.info("Setup loaded! (mock)")

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

        # Manual AI Trade Button or Continuous Mode
        if not st.session_state.ai_trading_active:
            if st.button("🎯 Let AI Trade Once", key="ai_trade_once"):
                trade, action = execute_ai_trade(current_price, st.session_state.current_step)
                if trade:
                    st.info(f"🤖 AI {action.title()} at ${current_price:.2f}")
                else:
                    st.info("🤖 AI chose to HOLD")
        else:
            # Continuous AI Trading Mode
            st.info("🚀 AI is trading continuously...")
            st.markdown("**Click 'Pause for Feedback' when you want to rate performance**")

            if st.button("⏸️ Pause for Feedback", key="pause_ai"):
                st.session_state.ai_trading_active = False
                st.rerun()

            # Auto-execute AI trade in continuous mode
            trade, action = execute_ai_trade(current_price, st.session_state.current_step)
            if trade:
                st.success(f"🚀 AI Auto-{action.title()} at ${current_price:.2f}")

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
            if st.session_state.current_step < len(st.session_state.data) - 1:
                st.session_state.current_step += 1
                st.rerun()

        # Auto-play mode with chart stability fix
        auto_play = st.checkbox("🎬 Auto-play", key="auto_play")
        if auto_play:
            time.sleep(1.0)  # Slower for stability
            if st.session_state.current_step < len(st.session_state.data) - 1:
                st.session_state.current_step += 1
                # Auto-execute AI trade if continuous mode is on
                if st.session_state.ai_trading_active:
                    execute_ai_trade(current_price, st.session_state.current_step)
                st.rerun()

    # Performance summary
    st.subheader("📈 Performance Comparison")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("👤 Human Trades", len(st.session_state.human_trades))

    with col2:
        st.metric("🤖 AI Trades", len(st.session_state.ai_trades))

    with col3:
        st.metric("💭 Feedback Given", len(st.session_state.feedback_history))

    with col4:
        st.metric("🎯 TP/SL Levels", len(st.session_state.tp_sl_boxes))

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