"""
Pure TradingView Lightweight Charts Trading App
Nur Lightweight Charts - Kein TradingView Widget
Mit Trading Features und AI Integration
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
from datetime import datetime, timedelta
import time

st.set_page_config(
    page_title="RL Trading - Lightweight Charts Only",
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
.symbol-item {
    background: #2a2e39;
    color: #d1d4dc;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid transparent;
}
.symbol-item:hover {
    background: #26a69a;
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(38, 166, 154, 0.3);
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
        'chart_id': 0,  # For forcing chart refresh
        'show_volume': True,
        'show_ma20': True,
        'show_ma50': False,
        'show_bollinger': False,
        'show_rsi': False,
        'drawing_mode': None,  # 'line', 'rect', 'trendline', etc.
        'show_symbol_modal': False,  # Symbol selection modal state
        'symbol_search': '',  # Search term for symbol filtering
        'pending_symbol_change': None,  # Track pending symbol changes
        'symbol_changed_via_modal': False,  # Flag to prevent sidebar override
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# Available Assets Configuration
AVAILABLE_ASSETS = {
    "stocks": [
        {"symbol": "AAPL", "name": "Apple Inc.", "description": "Technology - Consumer Electronics"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "description": "Technology - Software"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "description": "Technology - Internet Services"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "description": "Automotive - Electric Vehicles"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "description": "Consumer Discretionary - E-commerce"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "description": "Technology - Semiconductors"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "description": "Technology - Social Media"},
        {"symbol": "NFLX", "name": "Netflix Inc.", "description": "Entertainment - Streaming"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "description": "Technology - Semiconductors"},
        {"symbol": "CRM", "name": "Salesforce Inc.", "description": "Technology - Cloud Software"},
        {"symbol": "INTC", "name": "Intel Corporation", "description": "Technology - Semiconductors"},
        {"symbol": "BABA", "name": "Alibaba Group", "description": "Technology - E-commerce China"},
        {"symbol": "PYPL", "name": "PayPal Holdings", "description": "Financial - Digital Payments"},
        {"symbol": "DIS", "name": "The Walt Disney Company", "description": "Entertainment - Media"},
        {"symbol": "V", "name": "Visa Inc.", "description": "Financial - Payment Networks"},
        {"symbol": "MA", "name": "Mastercard Inc.", "description": "Financial - Payment Networks"}
    ],
    "crypto": [
        {"symbol": "BTC-USD", "name": "Bitcoin", "description": "Cryptocurrency - Digital Gold"},
        {"symbol": "ETH-USD", "name": "Ethereum", "description": "Cryptocurrency - Smart Contracts"},
        {"symbol": "ADA-USD", "name": "Cardano", "description": "Cryptocurrency - Proof of Stake"},
        {"symbol": "DOT-USD", "name": "Polkadot", "description": "Cryptocurrency - Interoperability"},
        {"symbol": "LINK-USD", "name": "Chainlink", "description": "Cryptocurrency - Oracle Network"},
        {"symbol": "LTC-USD", "name": "Litecoin", "description": "Cryptocurrency - Digital Silver"}
    ],
    "forex": [
        {"symbol": "EURUSD=X", "name": "EUR/USD", "description": "Euro vs US Dollar"},
        {"symbol": "GBPUSD=X", "name": "GBP/USD", "description": "British Pound vs US Dollar"},
        {"symbol": "USDJPY=X", "name": "USD/JPY", "description": "US Dollar vs Japanese Yen"},
        {"symbol": "USDCHF=X", "name": "USD/CHF", "description": "US Dollar vs Swiss Franc"}
    ],
    "indices": [
        {"symbol": "^GSPC", "name": "S&P 500", "description": "US Large Cap Index"},
        {"symbol": "^IXIC", "name": "NASDAQ Composite", "description": "US Tech Index"},
        {"symbol": "^DJI", "name": "Dow Jones Industrial", "description": "US Blue Chip Index"},
        {"symbol": "^RUT", "name": "Russell 2000", "description": "US Small Cap Index"}
    ]
}

def validate_symbol(symbol):
    """Check if symbol is in available assets"""
    for category in AVAILABLE_ASSETS.values():
        for asset in category:
            if asset["symbol"] == symbol:
                return True
    return False

def get_asset_info(symbol):
    """Get asset information from available assets"""
    for category in AVAILABLE_ASSETS.values():
        for asset in category:
            if asset["symbol"] == symbol:
                return asset
    return None

def get_yfinance_data(symbol, period="1d", interval="5m"):
    """Hole Live-Daten von Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)

        if hist.empty:
            return None

        # Timezone handling für TradingView
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

def create_trading_chart(data_dict, trades=None, show_volume=True, show_ma20=True, show_ma50=False, show_bollinger=False, selected_symbol="AAPL", selected_interval="1h"):
    """TradingView Lightweight Charts mit Trading Features und Indikatoren"""
    if not data_dict or data_dict['data'].empty:
        return "<div>Keine Daten verfügbar</div>"

    df = data_dict['data']

    chart_data = []
    volume_data = []

    # Prepare candlestick and volume data
    for idx, row in df.iterrows():
        unix_timestamp = int(idx.timestamp())

        chart_data.append({
            'time': unix_timestamp,
            'open': float(row['Open']),
            'high': float(row['High']),
            'low': float(row['Low']),
            'close': float(row['Close'])
        })

        if show_volume:
            volume_data.append({
                'time': unix_timestamp,
                'value': float(row['Volume']),
                'color': '#26a69a80' if row['Close'] >= row['Open'] else '#ef535080'
            })

    chart_data.sort(key=lambda x: x['time'])
    volume_data.sort(key=lambda x: x['time'])

    # Calculate indicators
    ma20_data = []
    ma50_data = []
    bb_upper_data = []
    bb_lower_data = []

    if show_ma20 and len(df) >= 20:
        ma20 = df['Close'].rolling(window=20).mean()
        for idx, value in ma20.items():
            if not np.isnan(value):
                ma20_data.append({
                    'time': int(idx.timestamp()),
                    'value': float(value)
                })

    if show_ma50 and len(df) >= 50:
        ma50 = df['Close'].rolling(window=50).mean()
        for idx, value in ma50.items():
            if not np.isnan(value):
                ma50_data.append({
                    'time': int(idx.timestamp()),
                    'value': float(value)
                })

    if show_bollinger and len(df) >= 20:
        ma = df['Close'].rolling(window=20).mean()
        std = df['Close'].rolling(window=20).std()
        bb_upper = ma + (std * 2)
        bb_lower = ma - (std * 2)

        for idx, (upper, lower) in zip(bb_upper.index, zip(bb_upper, bb_lower)):
            if not np.isnan(upper) and not np.isnan(lower):
                timestamp = int(idx.timestamp())
                bb_upper_data.append({'time': timestamp, 'value': float(upper)})
                bb_lower_data.append({'time': timestamp, 'value': float(lower)})

    chart_data.sort(key=lambda x: x['time'])

    # Prepare trades data
    trade_markers = []
    if trades:
        for trade in trades:
            try:
                # Find the corresponding candle timestamp
                trade_time = trade['timestamp']
                if isinstance(trade_time, (int, float)):
                    # If it's already a timestamp
                    marker_time = int(trade_time)
                else:
                    # If it's a datetime
                    marker_time = int(trade_time.timestamp())

                color = '#26a69a' if trade['type'] == 'buy' else '#ef5350'
                shape = 'arrowUp' if trade['type'] == 'buy' else 'arrowDown'

                trade_markers.append({
                    'time': marker_time,
                    'position': 'belowBar' if trade['type'] == 'buy' else 'aboveBar',
                    'color': color,
                    'shape': shape,
                    'text': f"{trade['source']} {trade['type'].upper()}"
                })
            except Exception as e:
                print(f"Error processing trade: {e}")

    js_data = json.dumps(chart_data)
    js_markers = json.dumps(trade_markers)
    js_volume = json.dumps(volume_data)
    js_ma20 = json.dumps(ma20_data)
    js_ma50 = json.dumps(ma50_data)
    js_bb_upper = json.dumps(bb_upper_data)
    js_bb_lower = json.dumps(bb_lower_data)

    # Generate unique chart ID to force refresh
    import time
    chart_id = f"trading_chart_{int(time.time() * 1000)}"

    widget_html = f"""
    <div style="width: 100%; height: 600px; background-color: #000000; position: relative; margin: 0; padding: 0; overflow: hidden;">

      <!-- Top Overlay Bar (Asset Symbol + Timeframes) -->
      <div style="position: absolute; top: 0; left: 0; right: 0; height: 28px; z-index: 1001; background: rgba(255, 255, 255, 0.95); border-bottom: 1px solid #ddd; display: flex; align-items: center; padding: 0;">

        <!-- Asset Symbol (clickable) -->
        <div onclick="document.getElementById('symbolModal').style.display='block'; console.log('Modal opened directly');" style="color: #26a69a; font-weight: bold; font-size: 14px; padding: 4px 8px; border-right: 1px solid #2a2e39; height: 100%; display: flex; align-items: center; cursor: pointer; transition: background-color 0.2s;"
             onmouseover="this.style.backgroundColor='rgba(38, 166, 154, 0.1)'"
             onmouseout="this.style.backgroundColor='transparent'"
             title="Click to change symbol - {get_asset_info(selected_symbol)['name'] if get_asset_info(selected_symbol) else 'Unknown Asset'}">
          {selected_symbol} ▼
        </div>

        <!-- Timeframe Buttons -->
        <div style="padding: 4px; color: #666; font-size: 12px;">
          {selected_symbol} • {selected_interval}
        </div>
      </div>

      <!-- Left Drawing Tools Panel -->
      <div id="drawing_tools" style="position: absolute; top: 28px; left: 0; width: 28px; z-index: 1000; background: rgba(255, 255, 255, 0.95); border-right: 1px solid #ddd; padding: 2px; display: flex; flex-direction: column; gap: 1px;">

        <button id="tool_cursor" onclick="setDrawingMode('cursor')" style="background: #ffffff; color: #000; border: none; padding: 2px; border-radius: 2px; font-size: 10px; cursor: pointer; width: 24px; height: 24px; font-weight: bold;" title="Cursor">
          🖱️
        </button>

        <button id="tool_line" onclick="setDrawingMode('line')" style="background: #ddd; color: #333; border: none; padding: 2px; border-radius: 2px; font-size: 10px; cursor: pointer; width: 24px; height: 24px;" title="Trend Line">
          📏
        </button>

        <button id="tool_rect" onclick="setDrawingMode('rect')" style="background: #ddd; color: #333; border: none; padding: 2px; border-radius: 2px; font-size: 10px; cursor: pointer; width: 24px; height: 24px;" title="Rectangle">
          ⬜
        </button>

        <button id="tool_circle" onclick="setDrawingMode('circle')" style="background: #ddd; color: #333; border: none; padding: 2px; border-radius: 2px; font-size: 10px; cursor: pointer; width: 24px; height: 24px;" title="Circle">
          🔵
        </button>

        <button id="tool_fib" onclick="setDrawingMode('fibonacci')" style="background: #ddd; color: #333; border: none; padding: 2px; border-radius: 2px; font-size: 10px; cursor: pointer; width: 24px; height: 24px;" title="Fibonacci">
          🌀
        </button>

        <div style="width: 100%; height: 1px; background: #333; margin: 1px 0;"></div>

        <button id="tool_clear" onclick="clearDrawings()" style="background: #ffffff; color: #ff0000; border: none; padding: 2px; border-radius: 2px; font-size: 9px; cursor: pointer; width: 24px; height: 24px; font-weight: bold;" title="Clear All">
          🗑️
        </button>

      </div>

      <!-- Hidden Top Controls Panel for remaining content -->
      <div id="chart_controls" style="display: none;">

        <!-- Timeframe Buttons -->

        <div style="width: 1px; height: 20px; background: #333;"></div>

        <!-- Indicator Toggles -->
        <button id="toggle_volume" onclick="toggleIndicatorReal('volume')" style="background: {'#26a69a' if show_volume else '#333'}; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;">
          📊 Vol
        </button>

        <button id="toggle_ma20" onclick="toggleIndicatorReal('ma20')" style="background: {'#ffeb3b' if show_ma20 else '#333'}; color: {'black' if show_ma20 else '#333'}; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;">
          📏 MA20
        </button>

        <button id="toggle_ma50" onclick="toggleIndicatorReal('ma50')" style="background: {'#ff9800' if show_ma50 else '#333'}; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;">
          📏 MA50
        </button>

        <button id="toggle_bb" onclick="toggleIndicatorReal('bollinger')" style="background: {'#9c27b0' if show_bollinger else '#333'}; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer;">
          📊 BB
        </button>

        <div style="width: 1px; height: 20px; background: #333;"></div>

        <!-- Trading Controls -->
        <button id="trade_buy" onclick="executeTradeReal('buy')" style="background: #26a69a; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: bold;">
          🟢 BUY
        </button>

        <button id="trade_sell" onclick="executeTradeReal('sell')" style="background: #ef5350; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: bold;">
          🔴 SELL
        </button>

        <button id="ai_signal" onclick="executeAITradeReal()" style="background: #2196f3; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 11px; cursor: pointer;">
          🤖 AI
        </button>

      </div>

      <!-- Price Display Overlay -->
      <div id="price_display" style="position: absolute; top: 10px; right: 10px; z-index: 1000; background: rgba(255, 255, 255, 0.9); border: 1px solid #ddd; border-radius: 6px; padding: 8px; color: #26a69a; font-size: 14px; font-weight: bold;">
        💰 $${{{data_dict['current_price']:.2f}}}
      </div>

      <!-- Status Bar -->
      <div id="status_bar" style="position: absolute; bottom: 10px; left: 10px; z-index: 1000; background: rgba(255, 255, 255, 0.9); border: 1px solid #ddd; border-radius: 6px; padding: 6px 12px; color: #999; font-size: 11px;">
        📊 {selected_symbol} • {selected_interval.upper()} • Ready
      </div>

      <!-- Symbol Selection Modal -->
      <div id="symbolModal" style="display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.7);">
        <div style="background-color: #1e2128; margin: 5% auto; padding: 0; border-radius: 8px; width: 90%; max-width: 600px; max-height: 80%; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">

          <!-- Modal Header -->
          <div style="background: #26a69a; padding: 15px 20px; border-radius: 8px 8px 0 0; display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0; color: white; font-size: 16px;">🔍 Select Trading Symbol</h3>
            <span onclick="document.getElementById('symbolModal').style.display='none';" style="color: white; font-size: 24px; font-weight: bold; cursor: pointer; padding: 0 5px;">&times;</span>
          </div>

          <!-- Search Box -->
          <div style="padding: 15px 20px; border-bottom: 1px solid #2a2e39;">
            <input type="text" id="symbolSearch" placeholder="Search symbols... (e.g. AAPL, MSFT, BTC)"
                   style="width: 100%; padding: 10px; border: 1px solid #2a2e39; border-radius: 4px; background: #0e1111; color: #d1d4dc; font-size: 14px;"
                   oninput="filterSymbols()">
          </div>

          <!-- Symbol Categories -->
          <div id="symbolCategories" style="padding: 20px;">
            <h4 style="color: #26a69a; margin: 15px 0 10px 0;">US Stocks</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; margin-bottom: 15px;">
              <div onclick="alert('Selected: AAPL'); document.getElementById('symbolModal').style.display='none';" style="padding: 8px; border: 1px solid #333; border-radius: 4px; cursor: pointer; background: #2a2e39; color: white;" onmouseover="this.style.background='#333'" onmouseout="this.style.background='#2a2e39'">
                <div style="font-weight: bold; font-size: 12px;">AAPL</div>
                <div style="font-size: 10px; color: #888;">Apple Inc.</div>
              </div>
              <div onclick="alert('Selected: TSLA'); document.getElementById('symbolModal').style.display='none';" style="padding: 8px; border: 1px solid #333; border-radius: 4px; cursor: pointer; background: #2a2e39; color: white;" onmouseover="this.style.background='#333'" onmouseout="this.style.background='#2a2e39'">
                <div style="font-weight: bold; font-size: 12px;">TSLA</div>
                <div style="font-size: 10px; color: #888;">Tesla Inc.</div>
              </div>
              <div onclick="alert('Selected: MSFT'); document.getElementById('symbolModal').style.display='none';" style="padding: 8px; border: 1px solid #333; border-radius: 4px; cursor: pointer; background: #2a2e39; color: white;" onmouseover="this.style.background='#333'" onmouseout="this.style.background='#2a2e39'">
                <div style="font-weight: bold; font-size: 12px;">MSFT</div>
                <div style="font-size: 10px; color: #888;">Microsoft</div>
              </div>
              <div onclick="alert('Selected: GOOGL'); document.getElementById('symbolModal').style.display='none';" style="padding: 8px; border: 1px solid #333; border-radius: 4px; cursor: pointer; background: #2a2e39; color: white;" onmouseover="this.style.background='#333'" onmouseout="this.style.background='#2a2e39'">
                <div style="font-weight: bold; font-size: 12px;">GOOGL</div>
                <div style="font-size: 10px; color: #888;">Alphabet Inc.</div>
              </div>
            </div>

            <h4 style="color: #26a69a; margin: 15px 0 10px 0;">Cryptocurrency</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; margin-bottom: 15px;">
              <div onclick="alert('Selected: BTC-USD'); document.getElementById('symbolModal').style.display='none';" style="padding: 8px; border: 1px solid #333; border-radius: 4px; cursor: pointer; background: #2a2e39; color: white;" onmouseover="this.style.background='#333'" onmouseout="this.style.background='#2a2e39'">
                <div style="font-weight: bold; font-size: 12px;">BTC-USD</div>
                <div style="font-size: 10px; color: #888;">Bitcoin</div>
              </div>
              <div onclick="alert('Selected: ETH-USD'); document.getElementById('symbolModal').style.display='none';" style="padding: 8px; border: 1px solid #333; border-radius: 4px; cursor: pointer; background: #2a2e39; color: white;" onmouseover="this.style.background='#333'" onmouseout="this.style.background='#2a2e39'">
                <div style="font-weight: bold; font-size: 12px;">ETH-USD</div>
                <div style="font-size: 10px; color: #888;">Ethereum</div>
              </div>
            </div>
          </div>

        </div>
      </div>


      <div id="{chart_id}" style="height: 600px;"></div>

      <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>

      <script>
        // GLOBAL MODAL FUNCTIONS - LOADED FIRST
        function openSymbolModal() {{
          console.log('🔵 Opening symbol modal...');
          const modal = document.getElementById('symbolModal');
          if (modal) {{
            console.log('📋 Generating asset categories...');
            generateSimpleCategories();
            modal.style.display = 'block';
            console.log('✅ Modal opened');
          }} else {{
            console.log('❌ Modal not found');
          }}
        }}

        function closeSymbolModal() {{
          console.log('🔵 Closing symbol modal...');
          const modal = document.getElementById('symbolModal');
          if (modal) {{
            modal.style.display = 'none';
            console.log('✅ Modal closed');
          }}
        }}

        function selectSymbol(symbol) {{
          console.log('🎯 Symbol selected:', symbol);
          alert('Selected: ' + symbol);
          closeSymbolModal();
        }}

        function generateSimpleCategories() {{
          console.log('📋 Generating simple asset categories...');
          const container = document.getElementById('symbolCategories');

          if (!container) {{
            console.log('❌ Categories container not found');
            return;
          }}

          // Simple hardcoded asset list
          const assets = {{
            'US Stocks': [
              {{'symbol': 'AAPL', 'name': 'Apple Inc.'}},
              {{'symbol': 'TSLA', 'name': 'Tesla Inc.'}},
              {{'symbol': 'MSFT', 'name': 'Microsoft'}},
              {{'symbol': 'GOOGL', 'name': 'Alphabet Inc.'}},
              {{'symbol': 'AMZN', 'name': 'Amazon'}}
            ],
            'Cryptocurrency': [
              {{'symbol': 'BTC-USD', 'name': 'Bitcoin'}},
              {{'symbol': 'ETH-USD', 'name': 'Ethereum'}},
              {{'symbol': 'ADA-USD', 'name': 'Cardano'}}
            ],
            'Forex': [
              {{'symbol': 'EURUSD=X', 'name': 'EUR/USD'}},
              {{'symbol': 'GBPUSD=X', 'name': 'GBP/USD'}}
            ]
          }};

          let html = '';

          Object.keys(assets).forEach(category => {{
            html += '<h4 style="color: #26a69a; margin: 15px 0 10px 0;">' + category + '</h4>';
            html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; margin-bottom: 15px;">';

            assets[category].forEach(asset => {{
              html += '<div onclick="selectSymbol(\'' + asset.symbol + '\')" ';
              html += 'style="padding: 8px; border: 1px solid #333; border-radius: 4px; cursor: pointer; background: #2a2e39; color: white;" ';
              html += 'onmouseover="this.style.background=\'#333\'" onmouseout="this.style.background=\'#2a2e39\'">';
              html += '<div style="font-weight: bold; font-size: 12px;">' + asset.symbol + '</div>';
              html += '<div style="font-size: 10px; color: #888;">' + asset.name + '</div>';
              html += '</div>';
            }});

            html += '</div>';
          }});

          container.innerHTML = html;
          console.log('✅ Simple categories generated');
        }}

        // Make functions immediately available
        window.openSymbolModal = openSymbolModal;
        window.closeSymbolModal = closeSymbolModal;
        window.selectSymbol = selectSymbol;
        window.generateSimpleCategories = generateSimpleCategories;

        console.log('✅ GLOBAL MODAL FUNCTIONS LOADED');
        console.log('openSymbolModal type:', typeof window.openSymbolModal);
      </script>

      <script>
        (function() {{
          console.log('🚀 Loading Trading Chart...');

          if (typeof LightweightCharts === 'undefined') {{
            console.error('❌ LightweightCharts not loaded!');
            document.getElementById('{chart_id}').innerHTML = '<div style="color: red; text-align: center; padding: 50px;">Error: Library not loaded</div>';
          }} else {{

          console.log('✅ LightweightCharts loaded');

          const container = document.getElementById('{chart_id}');
          if (!container) {{
            console.error('❌ Chart container not found!');
          }} else {{

          // Generate sample data for any symbol
          function generateSampleData(symbol) {{
            console.log('🎲 Generating sample data for:', symbol);

            const data = [];
            const now = Math.floor(Date.now() / 1000);
            const startTime = now - (365 * 24 * 60 * 60); // 1 Jahr zurück

            // Symbol-spezifische Basis-Preise
            const basePrices = {{
              'AAPL': 180,
              'TSLA': 250,
              'MSFT': 350,
              'GOOGL': 140,
              'AMZN': 145,
              'META': 300,
              'NVDA': 450,
              'BTC-USD': 45000,
              'ETH-USD': 2500,
              'EUR=X': 1.08,
              'GBP=X': 1.25,
              '^GSPC': 4500,
              '^IXIC': 15000
            }};

            let basePrice = basePrices[symbol] || 100;
            let currentPrice = basePrice;

            // Generiere 365 Tage Daten (täglich)
            for (let i = 0; i < 365; i++) {{
              const timestamp = startTime + (i * 24 * 60 * 60);

              // Realistische Preisbewegung
              const volatility = symbol.includes('BTC') || symbol.includes('ETH') ? 0.05 : 0.02;
              const priceChange = (Math.random() - 0.5) * volatility;

              const open = currentPrice;
              const close = open * (1 + priceChange);
              const high = Math.max(open, close) * (1 + Math.random() * 0.02);
              const low = Math.min(open, close) * (1 - Math.random() * 0.02);
              const volume = Math.random() * 1000000 + 500000;

              data.push({{
                time: timestamp,
                open: parseFloat(open.toFixed(2)),
                high: parseFloat(high.toFixed(2)),
                low: parseFloat(low.toFixed(2)),
                close: parseFloat(close.toFixed(2)),
                volume: Math.floor(volume)
              }});

              currentPrice = close;
            }}

            console.log('✅ Generated', data.length, 'data points for', symbol);
            return data;
          }}

          // Create chart als globale Variable
          window.chart = LightweightCharts.createChart(container, {{
            width: container.offsetWidth,
            height: 600,
            layout: {{
              backgroundColor: '#000000',
              textColor: '#d9d9d9'
            }},
            grid: {{
              vertLines: {{ visible: false }},
              horzLines: {{ visible: false }}
            }},
            timeScale: {{
              timeVisible: true,
              secondsVisible: false,
              borderColor: '#2a2e39',
              borderVisible: true,
              fixLeftEdge: true,
              fixRightEdge: true
            }},
            rightPriceScale: {{
              borderColor: '#2a2e39',
              borderVisible: true,
              scaleMargins: {{
                top: 0,
                bottom: 0
              }},
              entireTextOnly: true
            }},
            leftPriceScale: {{
              visible: false
            }},
            crosshair: {{
              mode: LightweightCharts.CrosshairMode.Normal
            }},
            handleScroll: {{
              mouseWheel: true,
              pressedMouseMove: true,
              horzTouchDrag: true,
              vertTouchDrag: true
            }},
            handleScale: {{
              axisPressedMouseMove: true,
              mouseWheel: true,
              pinch: true
            }}
          }});

          console.log('✅ Chart created');

          // Add candlestick series als globale Variable
          window.candlestickSeries = window.chart.addCandlestickSeries({{
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderUpColor: '#26a69a',
            borderDownColor: '#ef5350',
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350'
          }});

          // Set candlestick data
          const chartData = {js_data};
          console.log('📊 Setting chart data:', chartData.length, 'candles');

          if (chartData && chartData.length > 0) {{
            window.candlestickSeries.setData(chartData);
            console.log('✅ Candlestick data set');

            // Add volume series
            const volumeData = {js_volume};
            if (volumeData && volumeData.length > 0) {{
              window.volumeSeries = window.chart.addHistogramSeries({{
                color: '#26a69a',
                priceFormat: {{ type: 'volume' }},
                priceScaleId: '',
                scaleMargins: {{ top: 0.8, bottom: 0 }}
              }});
              window.volumeSeries.setData(volumeData);
              console.log('✅ Volume series added');
            }}

            // Add MA20
            const ma20Data = {js_ma20};
            if (ma20Data && ma20Data.length > 0) {{
              const ma20Series = chart.addLineSeries({{
                color: '#ffeb3b',
                lineWidth: 2,
                title: 'MA20'
              }});
              ma20Series.setData(ma20Data);
              console.log('✅ MA20 added');
            }}

            // Add MA50
            const ma50Data = {js_ma50};
            if (ma50Data && ma50Data.length > 0) {{
              const ma50Series = chart.addLineSeries({{
                color: '#ff9800',
                lineWidth: 2,
                title: 'MA50'
              }});
              ma50Series.setData(ma50Data);
              console.log('✅ MA50 added');
            }}

            // Add Bollinger Bands
            const bbUpperData = {js_bb_upper};
            const bbLowerData = {js_bb_lower};
            if (bbUpperData && bbUpperData.length > 0 && bbLowerData && bbLowerData.length > 0) {{
              const bbUpperSeries = chart.addLineSeries({{
                color: '#9c27b0',
                lineWidth: 1,
                lineStyle: 2, // Dashed
                title: 'BB Upper'
              }});
              bbUpperSeries.setData(bbUpperData);

              const bbLowerSeries = chart.addLineSeries({{
                color: '#9c27b0',
                lineWidth: 1,
                lineStyle: 2, // Dashed
                title: 'BB Lower'
              }});
              bbLowerSeries.setData(bbLowerData);
              console.log('✅ Bollinger Bands added');
            }}

            // Add trade markers
            const tradeMarkers = {js_markers};
            console.log('🎯 Adding trade markers:', tradeMarkers.length, 'trades');

            if (tradeMarkers && tradeMarkers.length > 0) {{
              candleSeries.setMarkers(tradeMarkers);
              console.log('✅ Trade markers added');
            }}

            // Fit chart
            chart.timeScale().fitContent();
            console.log('✅ Chart fitted');
          }} else {{
            console.error('❌ No chart data');
          }}

          // Auto-resize
          window.addEventListener('resize', () => {{
            chart.applyOptions({{ width: container.offsetWidth }});
          }});

          console.log('🎉 Trading chart ready!');

          }} // Close container check
          }} // Close library check

        }})();

        // In-Chart Control Functions
        function toggleIndicatorReal(indicator) {{
          console.log('Toggling indicator:', indicator);

          // Trigger Streamlit callback by creating a hidden input event
          const hiddenInput = document.createElement('input');
          hiddenInput.type = 'hidden';
          hiddenInput.name = 'indicator_toggle';
          hiddenInput.value = indicator;
          document.body.appendChild(hiddenInput);

          // Create custom event for Streamlit
          const event = new CustomEvent('streamlit:setComponentValue', {{
            detail: {{
              value: {{
                action: 'toggle_indicator',
                indicator: indicator,
                timestamp: Date.now()
              }}
            }}
          }});

          window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            value: {{
              action: 'toggle_indicator',
              indicator: indicator
            }}
          }}, '*');

          showNotification('📊 Toggling ' + indicator + ' indicator');
        }}


        function executeTradeReal(type) {{
          console.log('Executing trade:', type);

          window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            value: {{
              action: 'execute_trade',
              trade_type: type
            }}
          }}, '*');

          const color = type === 'buy' ? '#26a69a' : '#ef5350';
          showNotification('💼 ' + type.toUpperCase() + ' Trade executed', color);
        }}

        function executeAITradeReal() {{
          console.log('Executing AI trade');

          window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            value: {{
              action: 'ai_trade'
            }}
          }}, '*');

          showNotification('🤖 AI Signal generated', '#2196f3');
        }}

        function setDrawingMode(mode) {{
          console.log('Setting drawing mode:', mode);

          // Update button states
          const tools = ['cursor', 'line', 'rect', 'circle', 'fib'];
          tools.forEach(tool => {{
            const btn = document.getElementById('tool_' + tool);
            if (btn) {{
              btn.style.backgroundColor = tool === mode ? '#26a69a' : '#333';
            }}
          }});

          window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            value: {{
              action: 'set_drawing_mode',
              mode: mode
            }}
          }}, '*');

          showNotification('✏️ Drawing mode: ' + mode);
        }}

        function clearDrawings() {{
          console.log('Clearing all drawings');

          window.parent.postMessage({{
            type: 'streamlit:setComponentValue',
            value: {{
              action: 'clear_drawings'
            }}
          }}, '*');

          showNotification('🗑️ All drawings cleared', '#ef5350');
        }}

        function showNotification(message, color = '#26a69a') {{
          const notification = document.createElement('div');
          notification.innerHTML = message;
          notification.style.cssText = `
            position: absolute;
            top: 50px;
            right: 10px;
            z-index: 1001;
            background: ${{color}};
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
            animation: slideIn 0.3s ease-out;
          `;

          // Add animation CSS
          const style = document.createElement('style');
          style.textContent = `
            @keyframes slideIn {{
              from {{ transform: translateX(100%); opacity: 0; }}
              to {{ transform: translateX(0); opacity: 1; }}
            }}
          `;
          document.head.appendChild(style);

          document.querySelector('#{chart_id}').parentElement.appendChild(notification);

          // Remove after 2 seconds
          setTimeout(() => {{
            if (notification.parentElement) {{
              notification.remove();
            }}
          }}, 2000);
        }}

        // ========== EVENT-DRIVEN SYMBOL MANAGEMENT ==========

        // Single Source of Truth - Symbol Store
        class SymbolStore {{
          constructor() {{
            this.currentSymbol = '{selected_symbol}';
            this.listeners = [];
            this.availableAssets = {json.dumps(AVAILABLE_ASSETS)};
          }}

          // Subscribe to symbol changes
          subscribe(callback) {{
            this.listeners.push(callback);
          }}

          // Update symbol and notify all listeners
          setSymbol(newSymbol) {{
            console.log('🔄 setSymbol called with:', newSymbol);
            console.log('🔍 Current symbol:', this.currentSymbol);
            console.log('✅ Is valid symbol:', this.isValidSymbol(newSymbol));

            if (this.isValidSymbol(newSymbol) && newSymbol !== this.currentSymbol) {{
              console.log('📊 Symbol changing from ' + this.currentSymbol + ' to ' + newSymbol);
              this.currentSymbol = newSymbol;

              console.log('📢 Notifying ' + this.listeners.length + ' listeners...');
              // Notify all listeners (loose coupling)
              this.listeners.forEach(callback => {{
                try {{
                  console.log('📞 Calling listener...');
                  callback(newSymbol);
                }} catch (error) {{
                  console.error('Error in symbol change listener:', error);
                }}
              }});
              console.log('✅ All listeners notified');
            }} else {{
              console.log('❌ Symbol change rejected - invalid or same symbol');
            }}
          }}

          // Validate symbol against available assets
          isValidSymbol(symbol) {{
            const categories = Object.values(this.availableAssets);
            for (let i = 0; i < categories.length; i++) {{
              const category = categories[i];
              if (category.some(asset => asset.symbol === symbol)) {{
                return true;
              }}
            }}
            return false;
          }}

          // Get asset info
          getAssetInfo(symbol) {{
            const categories = Object.values(this.availableAssets);
            for (let i = 0; i < categories.length; i++) {{
              const category = categories[i];
              const asset = category.find(asset => asset.symbol === symbol);
              if (asset) return asset;
            }}
            return null;
          }}
        }}

        // Create global symbol store
        window.symbolStore = new SymbolStore();

        // ========== SYMBOL MODAL FUNCTIONS ==========

        window.openSymbolModal = function() {{
          console.log('Opening symbol modal...');
          const modal = document.getElementById('symbolModal');

          if (modal) {{
            console.log('Modal found, generating categories...');
            generateSymbolCategories();
            modal.style.display = 'block';
            console.log('Modal displayed');

            const searchInput = document.getElementById('symbolSearch');
            if (searchInput) {{
              searchInput.focus();
              console.log('Search input focused');
            }} else {{
              console.log('Search input not found');
            }}

            showNotification('Select a new trading symbol', '#2196f3');
          }} else {{
            console.log('Modal element not found!');
            alert('Modal not found - Please check console');
          }}
        }}

        window.closeSymbolModal = function() {{
          console.log('Closing symbol modal');
          const modal = document.getElementById('symbolModal');
          if (modal) {{
            modal.style.display = 'none';
            document.getElementById('symbolSearch').value = '';
            showAllSymbols();
          }}
        }}

        window.selectSymbol = function(symbol) {{
          console.log('🎯 selectSymbol called with:', symbol);

          // Event-driven update through SymbolStore
          console.log('📝 Calling symbolStore.setSymbol...');
          window.symbolStore.setSymbol(symbol);

          closeSymbolModal();
          showNotification('🎯 Symbol changed to ' + symbol, '#26a69a');
          console.log('✅ Modal closed and notification shown');
        }}

        window.generateSymbolCategories = function() {{
          console.log('🔵 Generating symbol categories...');
          const container = document.getElementById('symbolCategories');
          if (!container) {{
            console.log('❌ Symbol categories container not found');
            return;
          }}

          console.log('✅ Container found');
          console.log('Available assets:', window.symbolStore.availableAssets);

          const categoryConfig = {{
            'stocks': {{ title: '🏢 US Stocks', color: '#26a69a' }},
            'crypto': {{ title: '💰 Cryptocurrency', color: '#ff9800' }},
            'forex': {{ title: '💱 Forex', color: '#2196f3' }},
            'indices': {{ title: '📊 Indices', color: '#9c27b0' }}
          }};

          let html = '';
          let totalSymbols = 0;

          const categoryKeys = Object.keys(window.symbolStore.availableAssets);
          categoryKeys.forEach(categoryKey => {{
            const category = window.symbolStore.availableAssets[categoryKey];
            const config = categoryConfig[categoryKey];

            if (!config || !category || category.length === 0) return;

            html += `
              <div class="symbol-category" data-category="${{categoryKey}}">
                <h4 style="color: ${{config.color}}; margin: 0 0 10px 0; font-size: 14px;">${{config.title}}</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px; margin-bottom: 20px;">
            `;

            category.forEach(asset => {{
              const displayName = asset.symbol.includes('-USD') ? asset.symbol.replace('-USD', '') :
                                 asset.symbol.includes('=X') ? asset.name : asset.symbol;

              html += `
                <div class="symbol-item"
                     data-symbol="${{asset.symbol}}"
                     data-name="${{asset.name.toLowerCase()}}"
                     data-description="${{asset.description.toLowerCase()}}"
                     onclick="selectSymbol('${{asset.symbol}}')"
                     title="${{asset.name}} - ${{asset.description}}">
                  <div style="font-weight: bold; font-size: 12px;">${{displayName}}</div>
                  <div style="font-size: 10px; color: #888; margin-top: 2px;">${{asset.name}}</div>
                </div>
              `;
            }});

            html += `
                </div>
              </div>
            `;
          }});

          container.innerHTML = html;
          console.log('✅ Symbol categories generated with ' + totalSymbols + ' total symbols');
          console.log('HTML content length:', html.length);
        }}

        window.filterSymbols = function() {{
          const searchTerm = document.getElementById('symbolSearch').value.toLowerCase().trim();
          const symbolItems = document.querySelectorAll('.symbol-item');
          const categories = document.querySelectorAll('.symbol-category');

          if (searchTerm === '') {{
            showAllSymbols();
            return;
          }}

          let totalMatches = 0;

          symbolItems.forEach(item => {{
            const symbol = item.getAttribute('data-symbol').toLowerCase();
            const name = item.getAttribute('data-name');
            const description = item.getAttribute('data-description');

            const isMatch = symbol.includes(searchTerm) ||
                           name.includes(searchTerm) ||
                           description.includes(searchTerm);

            item.style.display = isMatch ? 'block' : 'none';
            if (isMatch) totalMatches++;
          }});

          // Hide empty categories
          categories.forEach(category => {{
            const visibleItems = category.querySelectorAll('.symbol-item[style=\"block\"], .symbol-item:not([style*=\"none\"])');
            category.style.display = visibleItems.length > 0 ? 'block' : 'none';
          }});

          console.log('🔍 Search for \"' + searchTerm + '\" found ' + totalMatches + ' matches');
        }}

        window.showAllSymbols = function() {{
          const symbolItems = document.querySelectorAll('.symbol-item');
          const categories = document.querySelectorAll('.symbol-category');

          symbolItems.forEach(item => {{
            item.style.display = 'block';
          }});

          categories.forEach(category => {{
            category.style.display = 'block';
          }});
        }}

        // ========== CHART SYMBOL LISTENER ==========

        // Subscribe chart to symbol changes (loose coupling)
        window.symbolStore.subscribe(function(newSymbol) {{
          console.log('🎯 Chart component received symbol change event:', newSymbol);

          // EINFACHES OBSERVER PATTERN - Direktes Chart Update!
          if (window.chart && window.chart.timeScale) {{
            console.log('📊 Updating chart data directly for:', newSymbol);

            // Chart Header aktualisieren
            const headerElement = document.querySelector('h3');
            if (headerElement) {{
              headerElement.textContent = `📈 ${{newSymbol}} - Live Trading Chart`;
              console.log('✅ Header updated to:', newSymbol);
            }} else {{
              console.log('❌ Header element not found');
            }}

            // Neue Sample-Daten für das neue Symbol generieren
            const newData = generateSampleData(newSymbol);
            console.log('📊 Generated new sample data for', newSymbol, ':', newData.length, 'candles');

            // Chart Series aktualisieren
            if (window.candlestickSeries) {{
              window.candlestickSeries.setData(newData);
              console.log('✅ Candlestick data updated');
            }}

            if (window.volumeSeries) {{
              const volumeData = newData.map(candle => ({{
                time: candle.time,
                value: candle.volume || Math.random() * 1000000,
                color: candle.close >= candle.open ? '#26a69a' : '#ef5350'
              }}));
              window.volumeSeries.setData(volumeData);
              console.log('✅ Volume data updated');
            }}

            // Chart an neue Daten anpassen
            window.chart.timeScale().fitContent();

            showNotification(`✅ Chart updated to ${{newSymbol}}`, '#26a69a');
            console.log('✅ Direct chart update completed!');
            return; // Kein Page Reload nötig!
          }}

          console.log('❌ Chart object not found, fallback to page reload...');

            setTimeout(function() {{
              // Method 1: Direct parent reload
              try {{
                if (window.top && window.top.location) {{
                  console.log('🔄 Method 1: Direct parent reload');
                  window.top.location.reload();
                  return;
                }}
              }} catch (e) {{
                console.log('❌ Method 1 failed:', e);
              }}

              // Method 2: Parent postMessage
              try {{
                console.log('🔄 Method 2: Parent postMessage');
                window.parent.postMessage({{
                  type: 'SYMBOL_CHANGE_REQUEST',
                  symbol: newSymbol,
                  timestamp: Date.now()
                }}, '*');
              }} catch (e) {{
                console.log('❌ Method 2 failed:', e);
              }}

              // Method 3: Current window reload as fallback
              try {{
                console.log('🔄 Method 3: Current window reload fallback');
                window.location.reload();
              }} catch (e) {{
                console.log('❌ Method 3 failed:', e);
              }}
            }}, 150);

          }} catch (error) {{
            console.log('❌ LocalStorage communication failed:', error);

            // Ultimate fallback: Try to manipulate parent URL directly
            try {{
              const currentUrl = window.top.location.href;
              const url = new URL(currentUrl);
              url.searchParams.set('new_symbol', newSymbol);
              window.top.location.href = url.href;
            }} catch (urlError) {{
              console.log('❌ URL manipulation failed, forcing reload...', urlError);
              window.top.location.reload();
            }}
          }}
        }});

        // Close modal when clicking outside
        window.onclick = function(event) {{
          const modal = document.getElementById('symbolModal');
          if (event.target === modal) {{
            closeSymbolModal();
          }}
        }}

        // Handle escape key
        document.addEventListener('keydown', function(event) {{
          if (event.key === 'Escape') {{
            closeSymbolModal();
          }}
        }});

        console.log('✅ Event-driven symbol management initialized');

        // Functions are already globally available above

        console.log('🌍 Modal functions made globally available');
        console.log('Available functions:', typeof window.openSymbolModal, typeof window.closeSymbolModal);

      </script>

    </div>
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

def handle_chart_callbacks():
    """Handle JavaScript callbacks from chart controls"""
    try:
        # Check for component value (JavaScript communication)
        if hasattr(st.session_state, 'chart_callback') and st.session_state.chart_callback:
            action_data = st.session_state.chart_callback
            action = action_data.get('action')

            if action == 'toggle_indicator':
                indicator = action_data.get('indicator')
                if indicator == 'volume':
                    st.session_state.show_volume = not st.session_state.show_volume
                elif indicator == 'ma20':
                    st.session_state.show_ma20 = not st.session_state.show_ma20
                elif indicator == 'ma50':
                    st.session_state.show_ma50 = not st.session_state.show_ma50
                elif indicator == 'bollinger':
                    st.session_state.show_bollinger = not st.session_state.show_bollinger
                st.session_state.chart_id += 1

            elif action == 'change_timeframe':
                timeframe = action_data.get('timeframe')
                if timeframe in ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']:
                    st.session_state.selected_interval = timeframe
                    st.session_state.live_data = None
                    st.session_state.chart_id += 1

            elif action == 'execute_trade':
                trade_type = action_data.get('trade_type')
                if st.session_state.trading_active and st.session_state.live_data:
                    current_price = st.session_state.live_data['current_price']
                    add_trade(trade_type, current_price, 'Chart')

            elif action == 'ai_trade':
                if st.session_state.trading_active and st.session_state.live_data:
                    ai_signal = generate_ai_signal()
                    if ai_signal and ai_signal['type'] in ['buy', 'sell']:
                        current_price = st.session_state.live_data['current_price']
                        add_trade(ai_signal['type'], current_price, 'AI')

            elif action == 'set_drawing_mode':
                mode = action_data.get('mode')
                st.session_state.drawing_mode = mode

            elif action == 'clear_drawings':
                # Reset drawing mode
                st.session_state.drawing_mode = None

            elif action == 'change_symbol':
                new_symbol = action_data.get('symbol')
                if new_symbol and new_symbol != st.session_state.selected_symbol:
                    # Validate symbol before switching
                    if validate_symbol(new_symbol):
                        # Update symbol and clear data to force refresh
                        st.session_state.selected_symbol = new_symbol
                        st.session_state.live_data = None
                        st.session_state.trades = []
                        st.session_state.human_trades = []
                        st.session_state.ai_trades = []
                        st.session_state.chart_id += 1
                        print(f"✅ Symbol changed to: {new_symbol}")
                    else:
                        print(f"❌ Invalid symbol rejected: {new_symbol}")

            # Clear the callback
            st.session_state.chart_callback = None

    except Exception as e:
        print(f"Callback error: {e}")

def main():
    init_session_state()

    # Handle any pending chart callbacks
    handle_chart_callbacks()

    st.title("🚀 RL Trading - Lightweight Charts Only")

    # Sidebar
    with st.sidebar:
        st.header("🎛️ Trading Controls")

        # Symbol Selection (using available assets)
        symbol_categories = {
            "🏢 US Stocks": [asset["symbol"] for asset in AVAILABLE_ASSETS["stocks"]],
            "💰 Crypto": [asset["symbol"] for asset in AVAILABLE_ASSETS["crypto"]],
            "💱 Forex": [asset["symbol"] for asset in AVAILABLE_ASSETS["forex"]],
            "📊 Indices": [asset["symbol"] for asset in AVAILABLE_ASSETS["indices"]]
        }

        selected_category = st.selectbox("Kategorie", list(symbol_categories.keys()))
        available_symbols = symbol_categories[selected_category]

        # Find current symbol's index in the available symbols
        current_index = 0
        if st.session_state.selected_symbol in available_symbols:
            current_index = available_symbols.index(st.session_state.selected_symbol)

        selected_symbol = st.selectbox("Symbol", available_symbols, index=current_index)

        # Only update symbol if it wasn't changed via modal
        if selected_symbol != st.session_state.selected_symbol and not st.session_state.symbol_changed_via_modal:
            st.session_state.selected_symbol = selected_symbol
            st.session_state.live_data = None
            st.session_state.trades = []
            st.session_state.human_trades = []
            st.session_state.ai_trades = []
            st.session_state.chart_id += 1

        # Reset the modal flag after one cycle
        if st.session_state.symbol_changed_via_modal:
            st.session_state.symbol_changed_via_modal = False

        # Timeframe
        interval_options = {
            "1m": "1m",
            "2m": "2m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h"
        }

        # Find current index
        current_index = 3  # Default to 5m
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
        st.info("🎛️ Use IN-CHART controls for indicators and trading!")

        # Status
        st.markdown("---")
        st.write(f"**Symbol:** {st.session_state.selected_symbol}")
        st.write(f"**Timeframe:** {selected_interval_name}")
        st.write(f"**Trading:** {'🟢 Active' if st.session_state.trading_active else '🔴 Inactive'}")

        if st.session_state.last_update:
            st.write(f"**Updated:** {st.session_state.last_update.strftime('%H:%M:%S')}")

        # Active Indicators
        active_indicators = []
        if st.session_state.show_volume: active_indicators.append("Volume")
        if st.session_state.show_ma20: active_indicators.append("MA20")
        if st.session_state.show_ma50: active_indicators.append("MA50")
        if st.session_state.show_bollinger: active_indicators.append("BB")

        if active_indicators:
            st.write(f"**Active:** {', '.join(active_indicators)}")

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
        st.subheader(f"📈 {st.session_state.selected_symbol} - Live Trading Chart")

        # Enhanced localStorage and postMessage handling for symbol changes
        enhanced_symbol_check_js = """
        <script>
        // Function to handle symbol change redirection
        function handleSymbolChange(newSymbol, source = 'unknown') {
            console.log('🎯 handleSymbolChange called:', { symbol: newSymbol, source: source });

            const url = new URL(window.location.href);
            url.searchParams.set('new_symbol', newSymbol);
            url.searchParams.set('change_source', source);

            console.log('🔄 Redirecting to:', url.href);
            window.location.href = url.href;
        }

        // Check localStorage for symbol change requests
        try {
            console.log('🔍 Checking localStorage for symbol changes...');
            const symbolChangeData = localStorage.getItem('streamlit_symbol_change');
            if (symbolChangeData) {
                const data = JSON.parse(symbolChangeData);
                console.log('📥 Found localStorage data:', data);

                if (!data.processed) {
                    console.log('✅ Processing unprocessed symbol change:', data.symbol);

                    // Mark as processed and clear immediately
                    localStorage.removeItem('streamlit_symbol_change');

                    // Trigger the change
                    handleSymbolChange(data.symbol, data.source || 'localStorage');
                } else {
                    console.log('⏭️ Symbol change already processed, skipping');
                }
            } else {
                console.log('📭 No localStorage symbol change data found');
            }
        } catch (error) {
            console.log('❌ localStorage check failed:', error);
        }

        // Listen for postMessage from iframe
        window.addEventListener('message', function(event) {
            console.log('📨 Received postMessage:', event.data);

            if (event.data && event.data.type === 'SYMBOL_CHANGE_REQUEST') {
                console.log('🎯 Processing SYMBOL_CHANGE_REQUEST:', event.data.symbol);

                // Clear any existing localStorage data to prevent conflicts
                localStorage.removeItem('streamlit_symbol_change');

                // Handle the symbol change
                handleSymbolChange(event.data.symbol, 'postMessage');
            }
        });

        console.log('✅ Enhanced symbol change handler initialized');
        </script>
        """
        st.components.v1.html(enhanced_symbol_check_js, height=0)

        # Check if there's a symbol change request in URL params (from Modal or localStorage)
        query_params = st.query_params
        if 'new_symbol' in query_params:
            new_symbol = query_params['new_symbol']
            change_source = query_params.get('change_source', 'unknown')

            if validate_symbol(new_symbol) and new_symbol != st.session_state.selected_symbol:
                print(f"🎯 Processing symbol change: {st.session_state.selected_symbol} → {new_symbol} (source: {change_source})")

                st.session_state.selected_symbol = new_symbol
                st.session_state.live_data = None
                st.session_state.trades = []
                st.session_state.human_trades = []
                st.session_state.ai_trades = []
                st.session_state.chart_id += 1
                # Mark that symbol was changed via modal
                st.session_state.symbol_changed_via_modal = True

                # Clear the query params and rerun
                st.query_params.clear()
                st.success(f"✅ Chart updated to {new_symbol} (via {change_source})")
                st.rerun()
            else:
                print(f"❌ Symbol change rejected: {new_symbol} (invalid or same symbol)")
                st.query_params.clear()

        # Chart fragment (only this part refreshes on timeframe change)
        @st.fragment
        def render_chart():
            # Timeframe buttons
            tf_cols = st.columns(7)
            intervals = ['1m', '2m', '5m', '15m', '30m', '1h', '4h']

            for i, interval in enumerate(intervals):
                with tf_cols[i]:
                    current = st.session_state.selected_interval == interval
                    button_type = "primary" if current else "secondary"
                    if st.button(interval, key=f"timeframe_{interval}", type=button_type, use_container_width=True):
                        if interval != st.session_state.selected_interval:
                            st.session_state.selected_interval = interval
                            st.session_state.live_data = None
                            st.session_state.chart_id += 1
                            st.rerun(fragment=True)  # Only refresh this fragment!

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
                # Create trading chart with markers
                chart_html = create_trading_chart(
                    st.session_state.live_data,
                    st.session_state.trades,
                    show_volume=st.session_state.show_volume,
                    show_ma20=st.session_state.show_ma20,
                    show_ma50=st.session_state.show_ma50,
                    show_bollinger=st.session_state.show_bollinger,
                    selected_symbol=st.session_state.selected_symbol,
                    selected_interval=st.session_state.selected_interval
                )

                # Display chart (key parameter not supported in streamlit components)
                st.components.v1.html(chart_html, height=620)

                # Chart info
                data_points = len(st.session_state.live_data['data'])
                trade_count = len(st.session_state.trades)
                st.info(f"📊 {data_points} candles | 🎯 {trade_count} trades")
            else:
                st.error("❌ Keine Daten verfügbar. Versuche anderes Symbol.")

        # Call the chart fragment
        render_chart()

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
            st.markdown("**👤 Your Actions:**")
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

            # Drawing Tools Section
            st.markdown("**🛠️ Drawing Tools:**")
            # TP/SL Tools Toggle
            if 'show_tp_sl_tools' not in st.session_state:
                st.session_state.show_tp_sl_tools = False

            st.session_state.show_tp_sl_tools = st.checkbox(
                "Show TP/SL Tools",
                value=st.session_state.show_tp_sl_tools,
                key="tp_sl_tools_toggle",
                help="Show Take Profit / Stop Loss drawing tools on chart"
            )

            if st.session_state.show_tp_sl_tools:
                col_tp, col_sl = st.columns(2)
                with col_tp:
                    st.button("🎯 Set TP", key="set_tp", help="Set Take Profit level")
                with col_sl:
                    st.button("🛑 Set SL", key="set_sl", help="Set Stop Loss level")

            # AI trading section
            st.markdown("**🤖 AI Actions:**")

            # Initialize AI trading state
            if 'ai_trading_active' not in st.session_state:
                st.session_state.ai_trading_active = False
            if 'ai_trades' not in st.session_state:
                st.session_state.ai_trades = []

            # Continuous AI Trading Toggle
            ai_was_active = st.session_state.ai_trading_active
            st.session_state.ai_trading_active = st.checkbox(
                "🔄 Continuous AI Trading",
                value=st.session_state.ai_trading_active,
                key="ai_continuous",
                help="AI will trade automatically until you stop it"
            )

            # Manual AI Trade Button
            if not st.session_state.ai_trading_active:
                if st.button("🎯 Let AI Trade Once", key="ai_trade_once"):
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

            # Current Signals section
            st.markdown("**📊 Current Signals:**")

            # Generate some basic signals based on indicators
            signals = {}

            # Simple moving average signals
            if len(data['data']) > 20:
                ma20 = data['data']['Close'].rolling(20).mean().iloc[-1]
                signals['above_ma20'] = current_price > ma20

            if len(data['data']) > 50:
                ma50 = data['data']['Close'].rolling(50).mean().iloc[-1]
                signals['above_ma50'] = current_price > ma50

            # Price trend
            if len(data['data']) > 5:
                price_5_ago = data['data']['Close'].iloc[-5]
                signals['bullish_trend'] = current_price > price_5_ago

            # Display signals
            if signals.get('above_ma20'):
                st.success("📈 Above MA20")
            if signals.get('above_ma50'):
                st.success("📊 Above MA50")
            if signals.get('bullish_trend'):
                st.success("🚀 Bullish Trend")

            if not any(signals.values()):
                st.info("⚖️ Neutral Signals")

            # Feedback section
            st.markdown("**💭 Feedback for AI:**")

            if 'ai_feedback' not in st.session_state:
                st.session_state.ai_feedback = "😐 Neutral"

            feedback = st.radio(
                "Rate AI's recent performance:",
                ["👍 Good", "👎 Bad", "😐 Neutral"],
                index=["👍 Good", "👎 Bad", "😐 Neutral"].index(st.session_state.ai_feedback),
                key="ai_feedback_radio",
                help="Your feedback helps improve AI performance"
            )

            if feedback != st.session_state.ai_feedback:
                st.session_state.ai_feedback = feedback
                st.success(f"Feedback updated: {feedback}")

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