"""
Quick Test für Live-Daten Integration
"""

import yfinance as yf
import pandas as pd
from datetime import datetime

def test_yfinance():
    """Test yfinance data fetch"""
    print("🧪 Testing yfinance data connection...")

    try:
        # Test verschiedene Symbole
        symbols = ["AAPL", "BTC-USD", "EURUSD=X"]

        for symbol in symbols:
            print(f"\n📊 Testing {symbol}...")

            ticker = yf.Ticker(symbol)

            # Hole 1-Tag Daten
            hist = ticker.history(period="1d", interval="5m")

            if not hist.empty:
                print(f"✅ {symbol}: {len(hist)} records")
                print(f"   Latest price: ${hist['Close'].iloc[-1]:.2f}")
                print(f"   Latest volume: {hist['Volume'].iloc[-1]:,.0f}")

                # Hole Info
                info = ticker.info
                if info:
                    print(f"   Company: {info.get('longName', 'N/A')}")
                    print(f"   Market Cap: {info.get('marketCap', 'N/A'):,}")
            else:
                print(f"❌ {symbol}: No data")

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

    return True

def test_tradingview_symbols():
    """Test TradingView symbol mapping"""
    print("\n🎯 Testing TradingView symbol mapping...")

    tv_symbols = {
        'AAPL': 'NASDAQ:AAPL',
        'MSFT': 'NASDAQ:MSFT',
        'BTC-USD': 'BINANCE:BTCUSDT',
        'ETH-USD': 'BINANCE:ETHUSDT',
        'EURUSD=X': 'FX:EURUSD'
    }

    for yf_symbol, tv_symbol in tv_symbols.items():
        print(f"✅ {yf_symbol} -> {tv_symbol}")

    return True

def test_data_format():
    """Test data format conversion for charts"""
    print("\n📈 Testing data format conversion...")

    try:
        ticker = yf.Ticker("AAPL")
        hist = ticker.history(period="1d", interval="5m")

        if not hist.empty:
            # Convert to chart format
            chart_data = []
            for idx, row in hist.iterrows():
                timestamp = int(idx.timestamp())
                chart_data.append({
                    'time': timestamp,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': float(row['Volume'])
                })

            print(f"✅ Converted {len(chart_data)} data points")
            print(f"   Sample: {chart_data[0]}")
            return True
        else:
            print("❌ No data to convert")
            return False

    except Exception as e:
        print(f"❌ Conversion error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Live Data Integration Test")
    print("=" * 50)

    # Run tests
    tests = [
        ("yfinance connection", test_yfinance),
        ("TradingView symbols", test_tradingview_symbols),
        ("Data format conversion", test_data_format)
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        result = test_func()
        results.append((test_name, result))

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY:")

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("You can now run: streamlit run streamlit_app_fixed_tradingview.py")
    else:
        print("\n⚠️  Some tests failed. Check your internet connection and try again.")