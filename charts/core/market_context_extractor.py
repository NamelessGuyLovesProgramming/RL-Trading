"""
Market Context Feature Extractor for RL Training
Berechnet die 7 Market-Context Features gemäß FEATURE_SPECIFICATION.md
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MarketContextExtractor:
    """
    Extrahiert Market-Context Features für RL Training

    Features (7 total):
    10. distance_to_ema20_pct: Abstand zu EMA-20 in %
    11. volume_ratio: Entry Volume / Ø-Volume(20)
    12. atr_value: Average True Range (14)
    13. recent_high_distance_pct: Abstand zu 50-Kerzen High
    14. recent_low_distance_pct: Abstand zu 50-Kerzen Low
    15. position_in_range: Position im 50-Kerzen Range (0-1)
    16. rr_ratio: Risk/Reward Ratio
    """

    def __init__(self):
        logger.info("[MarketContextExtractor] Initialized")

    def extract_at_entry(self, df: pd.DataFrame, entry_idx: int,
                         entry_price: float, sl_price: float, tp_price: float) -> Dict[str, float]:
        """
        Extrahiert alle Market-Context Features zum Entry-Zeitpunkt

        Args:
            df: DataFrame mit OHLC-Daten (Columns: open, high, low, close, volume)
            entry_idx: Index der Entry-Kerze
            entry_price: Entry Preis
            sl_price: Stop Loss Preis
            tp_price: Take Profit Preis

        Returns:
            Dict mit 7 Features
        """
        try:
            if entry_idx < 50:
                logger.warning(f"[MarketContextExtractor] Not enough data: idx={entry_idx} < 50")
                return self._get_default_features()

            features = {}

            # Feature 10: Distance to EMA-20
            features['distance_to_ema20_pct'] = self._calc_ema_distance(df, entry_idx, entry_price)

            # Feature 11: Volume Ratio
            features['volume_ratio'] = self._calc_volume_ratio(df, entry_idx)

            # Feature 12: ATR Value
            features['atr_value'] = self._calc_atr(df, entry_idx)

            # Features 13-15: Recent High/Low Distance & Position
            high_dist, low_dist, position = self._calc_range_features(df, entry_idx, entry_price)
            features['recent_high_distance_pct'] = high_dist
            features['recent_low_distance_pct'] = low_dist
            features['position_in_range'] = position

            # Feature 16: R:R Ratio
            features['rr_ratio'] = self._calc_rr_ratio(entry_price, sl_price, tp_price)

            logger.debug(f"[MarketContextExtractor] Extracted {len(features)} features at idx={entry_idx}")
            return features

        except Exception as e:
            logger.error(f"[MarketContextExtractor] Error extracting features: {e}", exc_info=True)
            return self._get_default_features()

    def _calc_ema_distance(self, df: pd.DataFrame, idx: int, entry_price: float) -> float:
        """
        Feature 10: Distance to EMA-20 in %
        Formula: (entry_price - ema20) / ema20 * 100
        """
        df_temp = df.copy()
        df_temp['ema_20'] = df_temp['close'].ewm(span=20, adjust=False).mean()

        ema_20 = df_temp.iloc[idx]['ema_20']
        distance_pct = ((entry_price - ema_20) / ema_20) * 100

        return round(distance_pct, 2)

    def _calc_volume_ratio(self, df: pd.DataFrame, idx: int) -> float:
        """
        Feature 11: Volume Ratio
        Formula: entry_volume / avg_volume_20
        """
        # Average Volume (letzte 20 Kerzen)
        start_idx = max(0, idx - 19)
        avg_volume = df['volume'].iloc[start_idx:idx + 1].mean()

        current_volume = df.iloc[idx]['volume']

        if avg_volume > 0:
            ratio = current_volume / avg_volume
        else:
            ratio = 1.0

        return round(ratio, 2)

    def _calc_atr(self, df: pd.DataFrame, idx: int) -> float:
        """
        Feature 12: Average True Range (14-period)

        ATR Formula:
        - True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        - ATR = Average of True Range over 14 periods
        """
        if idx < 14:
            return 0.0

        df_temp = df.copy()

        # Calculate True Range
        high_low = df_temp['high'] - df_temp['low']
        high_close = np.abs(df_temp['high'] - df_temp['close'].shift())
        low_close = np.abs(df_temp['low'] - df_temp['close'].shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

        # Calculate ATR (14-period rolling average)
        atr = true_range.rolling(window=14, min_periods=14).mean()

        atr_value = atr.iloc[idx]

        return round(atr_value, 2) if not pd.isna(atr_value) else 0.0

    def _calc_range_features(self, df: pd.DataFrame, idx: int, entry_price: float) -> tuple:
        """
        Features 13-15: Recent High/Low Distance & Position in Range

        Lookback: 50 Kerzen (~4 Stunden bei 5m Timeframe)

        Returns:
            (recent_high_distance_pct, recent_low_distance_pct, position_in_range)
        """
        lookback = 50
        start_idx = max(0, idx - lookback + 1)

        # Get recent high/low from last 50 candles (including current)
        recent_data = df.iloc[start_idx:idx + 1]
        recent_high = recent_data['high'].max()
        recent_low = recent_data['low'].min()

        # Feature 13: Distance to Recent High (%)
        high_distance_pct = ((entry_price - recent_high) / entry_price) * 100

        # Feature 14: Distance to Recent Low (%)
        low_distance_pct = ((entry_price - recent_low) / entry_price) * 100

        # Feature 15: Position in Range (0 = at low, 1 = at high)
        price_range = recent_high - recent_low
        if price_range > 0:
            position = (entry_price - recent_low) / price_range
        else:
            position = 0.5  # Default: middle

        return (
            round(high_distance_pct, 2),
            round(low_distance_pct, 2),
            round(position, 3)
        )

    def _calc_rr_ratio(self, entry_price: float, sl_price: float, tp_price: float) -> float:
        """
        Feature 16: Risk/Reward Ratio
        Formula: (tp - entry) / (entry - sl)
        """
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)

        if risk > 0:
            rr_ratio = reward / risk
        else:
            rr_ratio = 0.0

        return round(rr_ratio, 2)

    def _get_default_features(self) -> Dict[str, float]:
        """Returns default features when extraction fails"""
        return {
            'distance_to_ema20_pct': 0.0,
            'volume_ratio': 1.0,
            'atr_value': 0.0,
            'recent_high_distance_pct': 0.0,
            'recent_low_distance_pct': 0.0,
            'position_in_range': 0.5,
            'rr_ratio': 0.0
        }


def calculate_trade_features(df: pd.DataFrame, entry_time: str, exit_time: str,
                             entry_price: float, is_long: bool) -> Dict[str, any]:
    """
    Berechnet Trade-Specific Features (nach Trade-Close)

    Features:
    - trade_duration_candles: Anzahl Kerzen im Trade
    - max_drawdown_pct: Max Drawdown während Trade

    Args:
        df: DataFrame mit OHLC-Daten (Index muss timestamp sein)
        entry_time: Entry Timestamp (ISO string)
        exit_time: Exit Timestamp (ISO string)
        entry_price: Entry Preis
        is_long: True für Long, False für Short

    Returns:
        Dict mit trade_duration_candles, max_drawdown_pct
    """
    try:
        # Convert timestamps to datetime if needed
        entry_dt = pd.to_datetime(entry_time)
        exit_dt = pd.to_datetime(exit_time)

        # Match timezone awareness to DataFrame index
        # If DataFrame has UTC timezone, make timestamps UTC-aware
        # If DataFrame is timezone-naive, keep timestamps timezone-naive
        if df.index.tz is not None:
            # DataFrame is timezone-aware -> make timestamps timezone-aware
            if entry_dt.tz is None:
                entry_dt = entry_dt.tz_localize(df.index.tz)
            if exit_dt.tz is None:
                exit_dt = exit_dt.tz_localize(df.index.tz)
        else:
            # DataFrame is timezone-naive -> remove timezone from timestamps
            if entry_dt.tz is not None:
                entry_dt = entry_dt.replace(tzinfo=None)
            if exit_dt.tz is not None:
                exit_dt = exit_dt.replace(tzinfo=None)

        # Get candles between entry and exit
        mask = (df.index >= entry_dt) & (df.index <= exit_dt)
        trade_candles = df.loc[mask]

        if len(trade_candles) == 0:
            logger.warning(f"[TradeFeatures] No candles found between {entry_time} and {exit_time}")
            return {'trade_duration_candles': 0, 'max_drawdown_pct': 0.0}

        # Feature 7: Trade Duration in Candles
        duration = len(trade_candles)

        # Feature 9: Max Drawdown %
        if is_long:
            # Long: Drawdown is lowest low below entry
            lowest_price = trade_candles['low'].min()
            max_drawdown_pct = ((lowest_price - entry_price) / entry_price) * 100
        else:
            # Short: Drawdown is highest high above entry
            highest_price = trade_candles['high'].max()
            max_drawdown_pct = ((highest_price - entry_price) / entry_price) * 100

        return {
            'trade_duration_candles': duration,
            'max_drawdown_pct': round(max_drawdown_pct, 2)
        }

    except Exception as e:
        logger.error(f"[TradeFeatures] Error calculating: {e}", exc_info=True)
        return {'trade_duration_candles': 0, 'max_drawdown_pct': 0.0}
