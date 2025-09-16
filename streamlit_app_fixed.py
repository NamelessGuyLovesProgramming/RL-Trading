import streamlit as st
import sys
import pandas as pd
import json
import plotly.graph_objects as go
from datetime import datetime

# Add src to path for imports
sys.path.append('src')
from data_feed import create_sample_data

st.set_page_config(
    page_title="RL Trading - Fixed TradingView",
    page_icon="🚀",
    layout="wide"
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
.tradingview-container {
    width: 100%;
    height: 600px;
    background-color: #131722;
    border-radius: 8px;
    border: 1px solid #2B2B43;
}
</style>
""", unsafe_allow_html=True)

def get_ai_training_data(symbol="NQ", current_step=100, num_candles=200):
    """Get AI training data for the chart"""
    try:
        data = create_sample_data(symbol, periods=num_candles)
        data = data.reset_index(drop=True)
        return data.iloc[:current_step+1]
    except Exception as e:
        st.error(f"Error loading training data: {e}")
        return pd.DataFrame()

def create_lightweight_chart(data, current_step):
    """Create TradingView Lightweight Chart with better error handling"""
    if data.empty:
        return "<div style='color: red; padding: 20px;'>No data available</div>"

    # Convert data to chart format
    chart_data = []
    for idx in range(len(data)):
        row = data.iloc[idx]
        chart_data.append({
            'time': idx,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 1000))
        })

    js_data = json.dumps(chart_data)

    chart_html = f"""
    <div class="tradingview-container">
        <div id="lightweight_chart" style="height: 100%; width: 100%;"></div>
    </div>

    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <script>
    (function() {{
        try {{
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initChart);
            }} else {{
                initChart();
            }}

            function initChart() {{
                const container = document.getElementById('lightweight_chart');
                if (!container) {{
                    console.error('Chart container not found');
                    return;
                }}

                // Check if LightweightCharts is loaded
                if (typeof LightweightCharts === 'undefined') {{
                    container.innerHTML = '<div style="color: #ff6b6b; padding: 20px; text-align: center;">❌ TradingView library failed to load<br>Check internet connection</div>';
                    return;
                }}

                // Create chart
                const chart = LightweightCharts.createChart(container, {{
                    width: container.offsetWidth,
                    height: container.offsetHeight,
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
                const candleSeries = chart.addCandlestickSeries({{
                    upColor: '#26a69a',
                    downColor: '#ef5350',
                    borderVisible: false,
                    wickUpColor: '#26a69a',
                    wickDownColor: '#ef5350',
                }});

                const data = {js_data};
                candleSeries.setData(data);

                // Add MA20
                const ma20Data = [];
                let sum = 0;
                for (let i = 0; i < data.length; i++) {{
                    sum += data[i].close;
                    if (i >= 19) {{
                        if (i > 19) sum -= data[i-20].close;
                        ma20Data.push({{
                            time: data[i].time,
                            value: sum / Math.min(i+1, 20)
                        }});
                    }}
                }}

                if (ma20Data.length > 0) {{
                    const maSeries = chart.addLineSeries({{
                        color: '#ffeb3b',
                        lineWidth: 2,
                    }});
                    maSeries.setData(ma20Data);
                }}

                // Highlight current step
                const currentStep = {current_step};
                if (currentStep < data.length) {{
                    const currentPrice = data[currentStep].close;
                    const markerSeries = chart.addLineSeries({{
                        color: '#ff4757',
                        lineWidth: 3,
                    }});
                    markerSeries.setData([{{
                        time: currentStep,
                        value: currentPrice
                    }}]);
                }}

                // Auto-resize
                const resizeObserver = new ResizeObserver(entries => {{
                    if (entries.length === 0 || !entries[0].target) return;
                    const {{ width, height }} = entries[0].contentRect;
                    chart.applyOptions({{ width, height }});
                }});
                resizeObserver.observe(container);

                // Focus on current step
                const focusStart = Math.max(0, currentStep - 50);
                const focusEnd = Math.min(data.length - 1, currentStep + 10);
                chart.timeScale().setVisibleRange({{
                    from: data[focusStart].time,
                    to: data[focusEnd].time,
                }});

                console.log('✅ TradingView chart created successfully');
            }}
        }} catch (error) {{
            console.error('Chart creation failed:', error);
            const container = document.getElementById('lightweight_chart');
            if (container) {{
                container.innerHTML = `
                    <div style="color: #ff6b6b; padding: 20px; text-align: center;">
                        ❌ Chart Error: ${{error.message}}<br>
                        <small>Check browser console for details</small>
                    </div>
                `;
            }}
        }}
    }})();
    </script>
    """
    return chart_html

def create_plotly_chart(data, current_step, symbol):
    """Fallback Plotly chart"""
    if data.empty:
        return None

    fig = go.Figure()

    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['open'],
        high=data['high'],
        low=data['low'],
        close=data['close'],
        name=symbol,
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350'
    ))

    # MA20
    if len(data) >= 20:
        ma20 = data['close'].rolling(window=20).mean()
        fig.add_trace(go.Scatter(
            x=data.index,
            y=ma20,
            mode='lines',
            name='MA20',
            line=dict(color='#ffeb3b', width=2)
        ))

    # Current step marker
    if current_step < len(data):
        current_price = data.iloc[current_step]['close']
        fig.add_trace(go.Scatter(
            x=[current_step],
            y=[current_price],
            mode='markers',
            name='Current Step',
            marker=dict(color='#ff4757', size=12, symbol='diamond')
        ))

    # Chart styling
    fig.update_layout(
        template='plotly_dark',
        height=600,
        title=f"{symbol} - Step {current_step}",
        xaxis_title="Step",
        yaxis_title="Price",
        showlegend=True,
        xaxis=dict(rangeslider=dict(visible=False)),
        paper_bgcolor='#131722',
        plot_bgcolor='#131722'
    )

    # Focus on current area
    if len(data) > 50:
        focus_start = max(0, current_step - 50)
        focus_end = current_step + 10
        fig.update_xaxes(range=[focus_start, focus_end])

    return fig

def main():
    st.title("🚀 RL Trading System - Fixed TradingView Interface")

    # Initialize session state
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 50
    if 'trading_session_active' not in st.session_state:
        st.session_state.trading_session_active = False
    if 'feedback_history' not in st.session_state:
        st.session_state.feedback_history = []

    # Sidebar Controls
    with st.sidebar:
        st.header("Trading Controls")

        # Chart Type Selection
        chart_type = st.radio(
            "Chart Type",
            ["TradingView Lightweight", "Plotly Fallback"],
            help="Switch between TradingView and Plotly if chart doesn't load"
        )

        # Symbol Selection
        symbol_options = {"NQ": "NQ", "ES": "ES", "BTC": "BTC", "EUR": "EUR"}
        selected_symbol = st.selectbox("Symbol", list(symbol_options.keys()), index=0)

        # Step control
        new_step = st.slider("Current Step", 1, 200, st.session_state.current_step)
        if new_step != st.session_state.current_step:
            st.session_state.current_step = new_step

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

        # Status
        st.write(f"Step: {st.session_state.current_step}/200")
        st.write(f"Chart: {chart_type}")
        st.write(f"Session: {'Active' if st.session_state.trading_session_active else 'Inactive'}")

    # Main Content
    col1, col2 = st.columns([4, 1])

    with col1:
        st.subheader(f"📈 {selected_symbol} - Step {st.session_state.current_step}")

        # Get data
        data = get_ai_training_data(selected_symbol, st.session_state.current_step)

        if not data.empty:
            if chart_type == "TradingView Lightweight":
                # TradingView Chart
                chart_html = create_lightweight_chart(data, st.session_state.current_step)
                st.components.v1.html(chart_html, height=650)
            else:
                # Plotly Fallback
                fig = create_plotly_chart(data, st.session_state.current_step, selected_symbol)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

            # Price info
            current_price = data.iloc[-1]['close']
            prev_price = data.iloc[-2]['close'] if len(data) > 1 else current_price
            price_change = ((current_price - prev_price) / prev_price) * 100

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Current Price", f"${current_price:.2f}", f"{price_change:+.2f}%")
            with col_b:
                st.metric("Total Candles", len(data))
            with col_c:
                st.metric("Progress", f"{st.session_state.current_step}/200")
        else:
            st.error("Failed to load chart data")

    with col2:
        st.subheader("🧠 AI Feedback")

        if st.session_state.trading_session_active and not data.empty:
            # AI decision
            current_price = data.iloc[-1]['close']
            prev_price = data.iloc[-2]['close'] if len(data) > 1 else current_price

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
                    st.session_state.feedback_history.append({
                        'step': st.session_state.current_step,
                        'action': action,
                        'feedback': 'good'
                    })
                    st.success("Good feedback recorded!")
            with col_bad:
                if st.button("❌ Bad"):
                    st.session_state.feedback_history.append({
                        'step': st.session_state.current_step,
                        'action': action,
                        'feedback': 'bad'
                    })
                    st.error("Bad feedback recorded!")

            # Feedback stats
            if st.session_state.feedback_history:
                st.markdown("---")
                good_count = len([f for f in st.session_state.feedback_history if f['feedback'] == 'good'])
                bad_count = len([f for f in st.session_state.feedback_history if f['feedback'] == 'bad'])
                st.write(f"✅ Good: {good_count}")
                st.write(f"❌ Bad: {bad_count}")
        else:
            st.info("Start session for AI training")

if __name__ == "__main__":
    main()