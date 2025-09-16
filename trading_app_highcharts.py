"""
RL Trading App mit Highcharts Stock
Built-in Timeframe Controls und Drawing Tools
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime, timedelta
import time

st.set_page_config(
    page_title="RL Trading - Highcharts Stock",
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
        'chart_id': 0,
        'show_volume': True,
        'show_ma20': True,
        'show_ma50': False,
        'show_bollinger': False,
        'show_rsi': False
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

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
            'last_update': datetime.now(),
            'info': info
        }

    except Exception as e:
        st.error(f"Fehler beim Laden: {e}")
        return None

def create_highcharts_trading_chart(data_dict, trades=None):
    """Highcharts Stock Chart mit eingebauten Controls"""
    if not data_dict or data_dict['data'].empty:
        return "<div>Keine Daten verfügbar</div>"

    df = data_dict['data']

    # Prepare OHLCV data for Highcharts
    ohlc_data = []
    volume_data = []

    for idx, row in df.iterrows():
        timestamp = int(idx.timestamp() * 1000)  # Highcharts uses milliseconds

        ohlc_data.append([
            timestamp,
            float(row['Open']),
            float(row['High']),
            float(row['Low']),
            float(row['Close'])
        ])

        volume_data.append([
            timestamp,
            float(row['Volume'])
        ])

    # Calculate indicators
    indicators = {}

    if st.session_state.show_ma20 and len(df) >= 20:
        ma20 = df['Close'].rolling(window=20).mean()
        indicators['ma20'] = []
        for idx, value in ma20.items():
            if not np.isnan(value):
                indicators['ma20'].append([
                    int(idx.timestamp() * 1000),
                    float(value)
                ])

    if st.session_state.show_ma50 and len(df) >= 50:
        ma50 = df['Close'].rolling(window=50).mean()
        indicators['ma50'] = []
        for idx, value in ma50.items():
            if not np.isnan(value):
                indicators['ma50'].append([
                    int(idx.timestamp() * 1000),
                    float(value)
                ])

    # Prepare trade markers
    trade_markers = []
    if trades:
        for trade in trades:
            try:
                trade_time = trade['timestamp']
                if isinstance(trade_time, (int, float)):
                    marker_time = int(trade_time * 1000)
                else:
                    marker_time = int(trade_time.timestamp() * 1000)

                color = '#26a69a' if trade['type'] == 'buy' else '#ef5350'

                trade_markers.append({
                    'x': marker_time,
                    'title': '🟢' if trade['type'] == 'buy' else '🔴',
                    'text': f"{trade['source']} {trade['type'].upper()} @${trade['price']:.2f}"
                })
            except Exception as e:
                print(f"Error processing trade: {e}")

    chart_id = f"highcharts_chart_{st.session_state.chart_id}"

    widget_html = f"""
    <div style="width: 100%; height: 700px; background-color: #ffffff;">
      <div id="{chart_id}" style="width: 100%; height: 100%;"></div>
    </div>

    <script src="https://code.highcharts.com/stock/highstock.js"></script>
    <script src="https://code.highcharts.com/stock/modules/drag-panes.js"></script>
    <script src="https://code.highcharts.com/modules/annotations-advanced.js"></script>
    <script src="https://code.highcharts.com/modules/price-indicator.js"></script>
    <script src="https://code.highcharts.com/modules/full-screen.js"></script>
    <script src="https://code.highcharts.com/modules/stock-tools.js"></script>

    <script>
    (function() {{
        console.log('🚀 Loading Highcharts Stock Chart...');

        // Prepare data
        const ohlcData = {json.dumps(ohlc_data)};
        const volumeData = {json.dumps(volume_data)};
        const tradeMarkers = {json.dumps(trade_markers)};
        const indicators = {json.dumps(indicators)};

        // Chart configuration
        const chartConfig = {{
            chart: {{
                backgroundColor: '#ffffff',
                height: 700
            }},

            title: {{
                text: '{st.session_state.selected_symbol} - {st.session_state.selected_interval.upper()}',
                style: {{
                    color: '#333333',
                    fontSize: '18px'
                }}
            }},

            rangeSelector: {{
                enabled: true,
                buttons: [
                    {{ type: 'minute', count: 15, text: '15m' }},
                    {{ type: 'minute', count: 30, text: '30m' }},
                    {{ type: 'hour', count: 1, text: '1h' }},
                    {{ type: 'hour', count: 4, text: '4h' }},
                    {{ type: 'day', count: 1, text: '1d' }},
                    {{ type: 'all', text: 'All' }}
                ],
                selected: 4,
                inputEnabled: true
            }},

            navigator: {{
                enabled: true,
                height: 50
            }},

            scrollbar: {{
                enabled: true
            }},

            stockTools: {{
                gui: {{
                    enabled: true,
                    definitions: {{
                        simpleShapes: {{
                            items: ['label', 'circle', 'rectangle']
                        }},
                        lines: {{
                            items: ['segment', 'arrowSegment', 'ray', 'line', 'horizontalLine', 'verticalLine']
                        }},
                        crookedLines: {{
                            items: ['elliott3', 'elliott5', 'crooked3', 'crooked5']
                        }},
                        measure: {{
                            items: ['measureXY', 'measureX', 'measureY']
                        }},
                        advanced: {{
                            items: ['fibonacci', 'pitchfork', 'parallelChannel']
                        }},
                        toggles: {{
                            items: ['verticalToggle', 'horizontalToggle', 'lineToggle', 'arrowToggle', 'simpleShapes', 'flags']
                        }},
                        separator: {{
                            items: ['separator']
                        }},
                        fullScreen: {{
                            items: ['fullScreen']
                        }},
                        currentPriceIndicator: {{
                            items: ['currentPriceIndicator']
                        }}
                    }}
                }}
            }},

            plotOptions: {{
                candlestick: {{
                    upColor: '#26a69a',
                    color: '#ef5350'
                }}
            }},

            yAxis: [{{
                labels: {{
                    align: 'right',
                    x: -3
                }},
                title: {{
                    text: 'OHLC'
                }},
                height: '60%',
                lineWidth: 2,
                resize: {{
                    enabled: true
                }}
            }}, {{
                labels: {{
                    align: 'right',
                    x: -3
                }},
                title: {{
                    text: 'Volume'
                }},
                top: '65%',
                height: '35%',
                offset: 0,
                lineWidth: 2
            }}],

            tooltip: {{
                split: true
            }},

            series: [
                {{
                    type: 'candlestick',
                    name: '{st.session_state.selected_symbol}',
                    data: ohlcData,
                    dataGrouping: {{
                        units: [
                            ['minute', [1, 2, 3, 4, 5]],
                            ['hour', [1, 2, 3, 4, 6, 8, 12]],
                            ['day', [1]]
                        ]
                    }}
                }}
            ]
        }};

        // Add volume series
        if (volumeData && volumeData.length > 0) {{
            chartConfig.series.push({{
                type: 'column',
                name: 'Volume',
                data: volumeData,
                yAxis: 1,
                dataGrouping: {{
                    units: [
                        ['minute', [1, 2, 3, 4, 5]],
                        ['hour', [1, 2, 3, 4, 6, 8, 12]],
                        ['day', [1]]
                    ]
                }}
            }});
        }}

        // Add MA indicators
        if (indicators.ma20 && indicators.ma20.length > 0) {{
            chartConfig.series.push({{
                type: 'line',
                name: 'MA20',
                data: indicators.ma20,
                color: '#ffeb3b',
                lineWidth: 2
            }});
        }}

        if (indicators.ma50 && indicators.ma50.length > 0) {{
            chartConfig.series.push({{
                type: 'line',
                name: 'MA50',
                data: indicators.ma50,
                color: '#ff9800',
                lineWidth: 2
            }});
        }}

        // Create chart
        const chart = Highcharts.stockChart('{chart_id}', chartConfig);

        // Add trade flags/markers
        if (tradeMarkers && tradeMarkers.length > 0) {{
            chart.addSeries({{
                type: 'flags',
                name: 'Trades',
                data: tradeMarkers,
                onSeries: '{st.session_state.selected_symbol}',
                shape: 'squarepin',
                width: 16
            }});
        }}

        console.log('✅ Highcharts Stock Chart ready!');

        // Handle timeframe changes
        chart.rangeSelector.buttons.forEach((button, index) => {{
            button.element.addEventListener('click', function() {{
                console.log('Timeframe changed via range selector');
                // Communicate timeframe change to Streamlit if needed
                const timeframes = ['15m', '30m', '1h', '4h', '1d', 'all'];
                const newTimeframe = timeframes[index];

                window.parent.postMessage({{
                    type: 'streamlit:setComponentValue',
                    value: {{
                        action: 'change_timeframe',
                        timeframe: newTimeframe
                    }}
                }}, '*');
            }});
        }});

        // Handle trading actions
        window.executeTradeFromChart = function(tradeType) {{
            console.log('Executing trade from chart:', tradeType);

            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: {{
                    action: 'execute_trade',
                    trade_type: tradeType
                }}
            }}, '*');
        }};

    }})();
    </script>
    """

    return widget_html

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

        # Force chart refresh
        st.session_state.chart_id += 1

        return trade
    return None

def generate_ai_signal():
    """Simple AI trading signal based on moving average"""
    if not st.session_state.live_data:
        return None

    data = st.session_state.live_data['data']
    if len(data) < 20:
        return None

    # Simple MA crossover strategy
    ma_short = data['Close'].rolling(5).mean().iloc[-1]
    ma_long = data['Close'].rolling(20).mean().iloc[-1]
    current_price = data['Close'].iloc[-1]

    if ma_short > ma_long:
        return {'type': 'buy', 'signal': 'MA Crossover Bull', 'confidence': 0.7}
    elif ma_short < ma_long:
        return {'type': 'sell', 'signal': 'MA Crossover Bear', 'confidence': 0.6}
    else:
        return {'type': 'hold', 'signal': 'No clear signal', 'confidence': 0.3}

def main():
    init_session_state()

    st.title("🚀 RL Trading - Highcharts Stock (Built-in Controls)")

    # Sidebar
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
            st.session_state.live_data = None
            st.session_state.trades = []
            st.session_state.human_trades = []
            st.session_state.ai_trades = []

        # Timeframe
        interval_options = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h"
        }

        current_index = 1  # Default to 5m
        for i, interval in enumerate(interval_options.values()):
            if interval == st.session_state.selected_interval:
                current_index = i
                break

        selected_interval_name = st.selectbox("Timeframe", list(interval_options.keys()), index=current_index)
        if interval_options[selected_interval_name] != st.session_state.selected_interval:
            st.session_state.selected_interval = interval_options[selected_interval_name]
            st.session_state.live_data = None
            st.session_state.chart_id += 1

        st.markdown("---")

        # Data Controls
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh", type="primary"):
                st.session_state.live_data = None
                st.rerun()

        with col2:
            st.session_state.auto_refresh = st.checkbox("Auto 30s")

        # Trading Session
        if st.button("🎯 Toggle Trading", type="secondary"):
            st.session_state.trading_active = not st.session_state.trading_active
            st.rerun()

        st.markdown("---")

        # Indicator Controls
        st.subheader("📊 Indicators")
        st.session_state.show_volume = st.checkbox("Volume", value=st.session_state.show_volume)
        st.session_state.show_ma20 = st.checkbox("MA20", value=st.session_state.show_ma20)
        st.session_state.show_ma50 = st.checkbox("MA50", value=st.session_state.show_ma50)

        if st.button("🔄 Apply Indicators", type="secondary"):
            st.session_state.chart_id += 1
            st.rerun()

        st.markdown("---")
        st.info("🎨 Use built-in chart tools for drawing!")
        st.info("⏰ Use built-in range selector for timeframes!")

        # Status
        st.markdown("---")
        st.write(f"**Symbol:** {st.session_state.selected_symbol}")
        st.write(f"**Timeframe:** {selected_interval_name}")
        st.write(f"**Trading:** {'🟢 Active' if st.session_state.trading_active else '🔴 Inactive'}")

        if st.session_state.last_update:
            st.write(f"**Updated:** {st.session_state.last_update.strftime('%H:%M:%S')}")

        # Trade Stats
        if st.session_state.trades:
            st.markdown("---")
            st.write("**📊 Trade Stats:**")
            human_count = len(st.session_state.human_trades)
            ai_count = len(st.session_state.ai_trades)
            st.write(f"Human: {human_count} | AI: {ai_count}")

    # Main Content
    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"📈 {st.session_state.selected_symbol} - Professional Trading Chart")

        # Load data if needed
        if st.session_state.live_data is None:
            with st.spinner("Loading market data..."):
                period = "5d" if st.session_state.selected_interval in ["1m", "5m"] else "1mo"
                st.session_state.live_data = get_yfinance_data(
                    st.session_state.selected_symbol,
                    period=period,
                    interval=st.session_state.selected_interval
                )
                st.session_state.last_update = datetime.now()

        if st.session_state.live_data:
            # Create Highcharts trading chart
            chart_html = create_highcharts_trading_chart(
                st.session_state.live_data,
                st.session_state.trades
            )

            # Display chart
            st.components.v1.html(chart_html, height=720)

            # Chart info
            data_points = len(st.session_state.live_data['data'])
            trade_count = len(st.session_state.trades)
            st.info(f"📊 {data_points} candles | 🎯 {trade_count} trades | 🎨 Built-in drawing tools | ⏰ Built-in timeframe selector")
        else:
            st.error("❌ Keine Daten verfügbar. Versuche anderes Symbol.")

    with col2:
        st.subheader("🎮 Trading Controls")

        if st.session_state.live_data:
            data = st.session_state.live_data
            current_price = data['current_price']

            # Current Price Display
            last_close = data['data']['Close'].iloc[-2] if len(data['data']) > 1 else current_price
            price_change = current_price - last_close
            price_change_pct = (price_change / last_close) * 100
            color_class = "status-good" if price_change >= 0 else "status-bad"

            st.markdown(f"""
            <div class="data-panel">
                <h4>💰 Live Price</h4>
                <div class="metric-card">
                    <h2 class="{color_class}">${current_price:.2f}</h2>
                    <p class="{color_class}">
                        {'+' if price_change >= 0 else ''}{price_change:.2f}
                        ({'+' if price_change_pct >= 0 else ''}{price_change_pct:.2f}%)
                    </p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Human trading section
            st.markdown("**👤 Manual Trading:**")
            col_buy, col_sell = st.columns(2)
            with col_buy:
                if st.button("🟢 BUY", key="buy_btn", help=f"Buy at ${current_price:.2f}"):
                    trade = add_trade('buy', current_price, 'Human')
                    if trade:
                        st.success(f"✅ Buy ${current_price:.2f}")
                        st.rerun()

            with col_sell:
                if st.button("🔴 SELL", key="sell_btn", help=f"Sell at ${current_price:.2f}"):
                    trade = add_trade('sell', current_price, 'Human')
                    if trade:
                        st.success(f"✅ Sell ${current_price:.2f}")
                        st.rerun()

            # AI trading section
            st.markdown("**🤖 AI Trading:**")

            # Manual AI Trade Button
            if st.button("🎯 AI Signal", key="ai_trade_once"):
                ai_signal = generate_ai_signal()
                if ai_signal and ai_signal['type'] in ['buy', 'sell']:
                    trade = add_trade(ai_signal['type'], current_price, 'AI')
                    if trade:
                        st.info(f"🤖 AI {ai_signal['type'].upper()} - {ai_signal['signal']}")
                        st.rerun()
                else:
                    st.warning("🤖 AI: Hold signal")

            # Current AI Signal Display
            ai_signal = generate_ai_signal()
            if ai_signal:
                signal_color = {
                    'buy': 'status-good',
                    'sell': 'status-bad',
                    'hold': 'status-neutral'
                }.get(ai_signal['type'], 'status-neutral')

                st.markdown(f"""
                <div class="data-panel">
                    <h4>🤖 AI Signal</h4>
                    <div class="metric-card">
                        <p class="{signal_color}"><strong>{ai_signal['type'].upper()}</strong></p>
                        <p>{ai_signal['signal']}</p>
                        <p>Confidence: {ai_signal['confidence']:.1%}</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**🎨 Professional Features:**")
            st.success("✅ Built-in drawing tools")
            st.success("✅ Built-in timeframe selector")
            st.success("✅ Built-in technical indicators")
            st.success("✅ Professional navigation")
            st.success("✅ Full-screen mode")

        else:
            st.info("🎯 Activate trading to start trading")

        # Recent Trades
        if st.session_state.trades:
            st.markdown("**📈 Recent Trades:**")
            recent_trades = st.session_state.trades[-5:]  # Last 5 trades

            for trade in reversed(recent_trades):
                emoji = "🟢" if trade['type'] == 'buy' else "🔴"
                source_emoji = "👤" if trade['source'] == 'Human' else "🤖"
                time_str = trade['timestamp'].strftime('%H:%M:%S')
                st.write(f"{emoji} {source_emoji} {trade['type'].upper()} ${trade['price']:.2f} at {time_str}")

    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(30)
        st.session_state.live_data = None
        st.rerun()

if __name__ == "__main__":
    main()