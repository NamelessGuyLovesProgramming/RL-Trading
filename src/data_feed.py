"""
Live Data Feed System für RL Trading
Binance Integration mit WebSocket und Historical Data
"""

import asyncio
import websockets
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Callable, Optional
import threading
import time
from datetime import datetime, timedelta
import ccxt
import queue
import logging
from dataclasses import dataclass


@dataclass
class KlineData:
    """Structure for kline/candlestick data"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str


class DataBuffer:
    """Thread-safe buffer for storing market data"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.data = queue.Queue(maxsize=max_size)
        self.latest_data = {}
        self.lock = threading.Lock()

    def add_kline(self, kline: KlineData):
        """Add new kline data to buffer"""
        with self.lock:
            # Update latest data
            key = f"{kline.symbol}_{kline.timeframe}"
            self.latest_data[key] = kline

            # Add to queue (remove oldest if full)
            try:
                self.data.put_nowait(kline)
            except queue.Full:
                try:
                    self.data.get_nowait()  # Remove oldest
                    self.data.put_nowait(kline)
                except queue.Empty:
                    pass

    def get_latest(self, symbol: str, timeframe: str) -> Optional[KlineData]:
        """Get latest kline for symbol/timeframe"""
        with self.lock:
            key = f"{symbol}_{timeframe}"
            return self.latest_data.get(key)

    def get_all_data(self) -> List[KlineData]:
        """Get all data from buffer"""
        with self.lock:
            data_list = []
            temp_queue = queue.Queue()

            # Extract all data
            while not self.data.empty():
                try:
                    item = self.data.get_nowait()
                    data_list.append(item)
                    temp_queue.put(item)
                except queue.Empty:
                    break

            # Restore data to queue
            self.data = temp_queue
            return data_list


class BinanceDataFeed:
    """
    Binance Data Feed mit WebSocket und REST API
    """

    def __init__(self,
                 symbols: List[str] = ["NQ", "BTCUSDT", "ETHUSDT"],
                 timeframes: List[str] = ["1m", "5m", "15m"],
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None):

        self.symbols = [s.upper() for s in symbols]
        self.timeframes = timeframes
        self.api_key = api_key
        self.api_secret = api_secret

        # Initialize CCXT exchange
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'sandbox': False,  # Use True for testnet
            'enableRateLimit': True,
        })

        # Data storage
        self.data_buffer = DataBuffer()
        self.historical_data = {}  # symbol_timeframe -> DataFrame

        # WebSocket management
        self.ws_connections = {}
        self.ws_running = False
        self.ws_threads = []

        # Callbacks
        self.on_kline_callbacks = []

        # Logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def add_kline_callback(self, callback: Callable[[KlineData], None]):
        """Add callback for new kline data"""
        self.on_kline_callbacks.append(callback)

    def _notify_callbacks(self, kline: KlineData):
        """Notify all callbacks of new kline"""
        for callback in self.on_kline_callbacks:
            try:
                callback(kline)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")

    async def _kline_websocket(self, symbol: str, timeframe: str):
        """WebSocket connection for kline data"""

        # Convert timeframe for Binance
        interval_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d'
        }
        interval = interval_map.get(timeframe, '1m')

        # WebSocket URL
        stream = f"{symbol.lower()}@kline_{interval}"
        url = f"wss://stream.binance.com:9443/ws/{stream}"

        max_retries = 5
        retry_count = 0

        while self.ws_running and retry_count < max_retries:
            try:
                self.logger.info(f"Connecting to {symbol} {timeframe} WebSocket...")

                async with websockets.connect(url) as websocket:
                    retry_count = 0  # Reset on successful connection
                    self.logger.info(f"Connected to {symbol} {timeframe}")

                    async for message in websocket:
                        if not self.ws_running:
                            break

                        try:
                            data = json.loads(message)
                            kline_data = data.get('k', {})

                            if kline_data:
                                kline = KlineData(
                                    timestamp=int(kline_data['t']),
                                    open=float(kline_data['o']),
                                    high=float(kline_data['h']),
                                    low=float(kline_data['l']),
                                    close=float(kline_data['c']),
                                    volume=float(kline_data['v']),
                                    symbol=symbol,
                                    timeframe=timeframe
                                )

                                # Add to buffer
                                self.data_buffer.add_kline(kline)

                                # Notify callbacks
                                self._notify_callbacks(kline)

                        except json.JSONDecodeError:
                            self.logger.error(f"JSON decode error for {symbol}")
                        except Exception as e:
                            self.logger.error(f"Processing error: {e}")

            except Exception as e:
                retry_count += 1
                self.logger.error(f"WebSocket error for {symbol} {timeframe}: {e}")
                if retry_count < max_retries:
                    self.logger.info(f"Retrying in 5 seconds... ({retry_count}/{max_retries})")
                    await asyncio.sleep(5)
                else:
                    self.logger.error(f"Max retries reached for {symbol} {timeframe}")
                    break

    def start_websocket(self):
        """Start WebSocket connections for all symbols/timeframes"""
        if self.ws_running:
            self.logger.warning("WebSocket already running")
            return

        self.ws_running = True
        self.logger.info("Starting WebSocket connections...")

        # Create event loop for WebSocket connections
        def run_websockets():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Create tasks for all symbol/timeframe combinations
            tasks = []
            for symbol in self.symbols:
                for timeframe in self.timeframes:
                    task = loop.create_task(self._kline_websocket(symbol, timeframe))
                    tasks.append(task)

            try:
                loop.run_until_complete(asyncio.gather(*tasks))
            except Exception as e:
                self.logger.error(f"WebSocket loop error: {e}")
            finally:
                loop.close()

        # Start WebSocket thread
        ws_thread = threading.Thread(target=run_websockets, daemon=True)
        ws_thread.start()
        self.ws_threads.append(ws_thread)

    def stop_websocket(self):
        """Stop WebSocket connections"""
        self.logger.info("Stopping WebSocket connections...")
        self.ws_running = False

        # Wait for threads to finish
        for thread in self.ws_threads:
            thread.join(timeout=5)

        self.ws_threads.clear()
        self.logger.info("WebSocket connections stopped")

    def get_historical_data(self,
                          symbol: str,
                          timeframe: str,
                          limit: int = 1000,
                          start_time: Optional[datetime] = None) -> pd.DataFrame:
        """
        Fetch historical kline data from Binance REST API
        """
        try:
            # Prepare parameters
            params = {
                'symbol': symbol.upper(),
                'interval': timeframe,
                'limit': min(limit, 1000)  # Binance limit is 1000
            }

            if start_time:
                params['startTime'] = int(start_time.timestamp() * 1000)

            # Fetch data using CCXT
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol.upper(),
                timeframe=timeframe,
                limit=params['limit'],
                since=params.get('startTime')
            )

            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')

            # Store in cache
            key = f"{symbol}_{timeframe}"
            self.historical_data[key] = df

            self.logger.info(f"Fetched {len(df)} records for {symbol} {timeframe}")
            return df

        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            return pd.DataFrame()

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for symbol"""
        try:
            ticker = self.exchange.fetch_ticker(symbol.upper())
            return ticker['last']
        except Exception as e:
            self.logger.error(f"Error fetching latest price: {e}")
            return None

    def get_live_data_df(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """
        Get recent live data as DataFrame
        """
        data_list = self.data_buffer.get_all_data()

        # Filter for specific symbol and timeframe
        filtered_data = [
            d for d in data_list
            if d.symbol == symbol and d.timeframe == timeframe
        ]

        # Sort by timestamp
        filtered_data.sort(key=lambda x: x.timestamp)

        # Take last N records
        filtered_data = filtered_data[-limit:] if len(filtered_data) > limit else filtered_data

        if not filtered_data:
            return pd.DataFrame()

        # Convert to DataFrame
        df_data = []
        for kline in filtered_data:
            df_data.append({
                'timestamp': datetime.fromtimestamp(kline.timestamp / 1000),
                'open': kline.open,
                'high': kline.high,
                'low': kline.low,
                'close': kline.close,
                'volume': kline.volume
            })

        df = pd.DataFrame(df_data)
        df = df.set_index('timestamp')

        return df

    def get_combined_data(self, symbol: str, timeframe: str, live_limit: int = 50) -> pd.DataFrame:
        """
        Combine historical and live data
        """
        # Get historical data (if not cached, fetch it)
        key = f"{symbol}_{timeframe}"
        if key not in self.historical_data:
            self.get_historical_data(symbol, timeframe, limit=500)

        historical_df = self.historical_data.get(key, pd.DataFrame())
        live_df = self.get_live_data_df(symbol, timeframe, live_limit)

        if historical_df.empty:
            return live_df

        if live_df.empty:
            return historical_df

        # Combine data, avoiding duplicates
        combined_df = pd.concat([historical_df, live_df])
        combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
        combined_df = combined_df.sort_index()

        return combined_df


class TradingDataManager:
    """
    High-level manager for trading data
    """

    def __init__(self,
                 symbols: List[str] = ["NQ"],
                 primary_timeframe: str = "5m",
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None):

        self.symbols = symbols
        self.primary_timeframe = primary_timeframe

        # Initialize data feed
        self.data_feed = BinanceDataFeed(
            symbols=symbols,
            timeframes=[primary_timeframe, "1m", "15m"],
            api_key=api_key,
            api_secret=api_secret
        )

        # Current data cache
        self.current_data = {}
        self.update_callbacks = []

        # Setup callback
        self.data_feed.add_kline_callback(self._on_new_kline)

    def add_update_callback(self, callback: Callable[[str, pd.DataFrame], None]):
        """Add callback for data updates"""
        self.update_callbacks.append(callback)

    def _on_new_kline(self, kline: KlineData):
        """Handle new kline data"""
        if kline.timeframe == self.primary_timeframe:
            # Update current data
            df = self.data_feed.get_combined_data(kline.symbol, kline.timeframe)
            self.current_data[kline.symbol] = df

            # Notify callbacks
            for callback in self.update_callbacks:
                try:
                    callback(kline.symbol, df)
                except Exception as e:
                    logging.error(f"Update callback error: {e}")

    def start(self):
        """Start data collection"""
        logging.info("Starting trading data manager...")

        # Load initial historical data
        for symbol in self.symbols:
            df = self.data_feed.get_historical_data(symbol, self.primary_timeframe)
            if not df.empty:
                self.current_data[symbol] = df

        # Start live feed
        self.data_feed.start_websocket()
        logging.info("Trading data manager started")

    def stop(self):
        """Stop data collection"""
        self.data_feed.stop_websocket()
        logging.info("Trading data manager stopped")

    def get_current_data(self, symbol: str) -> pd.DataFrame:
        """Get current data for symbol"""
        return self.current_data.get(symbol, pd.DataFrame())

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price"""
        return self.data_feed.get_latest_price(symbol)


def create_sample_data(symbol: str = "NQ",
                      periods: int = 1000,
                      freq: str = "5min") -> pd.DataFrame:
    """
    Create sample data for testing (when no API access)
    """
    np.random.seed(42)

    # Generate timestamps
    end_time = datetime.now()
    timestamps = pd.date_range(
        end=end_time,
        periods=periods,
        freq=freq
    )

    # Simulate realistic price data
    # Set initial prices based on symbol
    if symbol.startswith("BTC"):
        initial_price = 45000
    elif symbol.startswith("ETH"):
        initial_price = 3000
    elif symbol == "NQ" or symbol.startswith("NQ"):
        initial_price = 15000  # Nasdaq futures around 15000
    else:
        initial_price = 1000

    # Random walk with trend and volatility
    returns = np.random.normal(0.0001, 0.02, periods)  # Small positive drift
    prices = [initial_price]

    for ret in returns[1:]:
        # Add some momentum and mean reversion
        momentum = np.sign(returns[len(prices)-1]) * 0.0005
        mean_reversion = -0.0001 * (prices[-1] / initial_price - 1)
        adjusted_return = ret + momentum + mean_reversion

        new_price = prices[-1] * (1 + adjusted_return)
        prices.append(new_price)

    # Generate OHLC from prices
    df_data = []
    for i, (timestamp, close) in enumerate(zip(timestamps, prices)):
        # Generate realistic OHLC
        volatility = abs(np.random.normal(0, 0.01))

        high = close * (1 + volatility)
        low = close * (1 - volatility)

        if i > 0:
            open_price = prices[i-1]
        else:
            open_price = close

        volume = np.random.randint(100, 1000) * 1000

        df_data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    df = pd.DataFrame(df_data, index=timestamps)
    return df


# Example usage and testing
if __name__ == "__main__":
    # Test with sample data
    print("Creating sample data...")
    sample_df = create_sample_data("NQ", periods=500)
    print(f"Sample data shape: {sample_df.shape}")
    print(sample_df.head())

    # Test data feed (requires API keys)
    # data_manager = TradingDataManager(["BTCUSDT"])
    # data_manager.start()
    #
    # # Wait and get some data
    # time.sleep(10)
    # current_data = data_manager.get_current_data("BTCUSDT")
    # print(f"Live data shape: {current_data.shape}")
    #
    # data_manager.stop()