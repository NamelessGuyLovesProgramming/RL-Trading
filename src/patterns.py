"""
Trading Pattern Detection System
Erkennt FVG, Order Blocks, Liquidity Zones und andere Trading Patterns
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import matplotlib.pyplot as plt


@dataclass
class PatternInfo:
    """Struktur für Pattern-Informationen"""
    pattern_type: str
    confidence: float
    price_level: float
    direction: str  # 'bullish', 'bearish', 'neutral'
    strength: float
    metadata: Dict


class PatternDetector:
    """Basis-Klasse für Pattern Detection"""
    def __init__(self, name: str):
        self.name = name

    def detect(self, df: pd.DataFrame, current_idx: int) -> Tuple[bool, Optional[PatternInfo]]:
        raise NotImplementedError


class FVGDetector(PatternDetector):
    """
    Fair Value Gap (FVG) Detector
    Erkennt Preislücken die als "Magnet" für zukünftige Preisbewegungen wirken
    """
    def __init__(self, min_gap_percent=0.1):
        super().__init__("FVG")
        self.min_gap_percent = min_gap_percent
        self.active_fvgs = []  # Liste aktiver FVGs

    def detect(self, df: pd.DataFrame, current_idx: int) -> Tuple[bool, Optional[PatternInfo]]:
        if current_idx < 3:
            return False, None

        # 3-Kerzen FVG Pattern
        candle1 = df.iloc[current_idx - 2]
        candle2 = df.iloc[current_idx - 1]  # Middle candle
        candle3 = df.iloc[current_idx]

        # Bullish FVG: Gap zwischen candle1.high und candle3.low
        if candle1['high'] < candle3['low']:
            gap_size = candle3['low'] - candle1['high']
            gap_percent = gap_size / candle1['high'] * 100

            if gap_percent >= self.min_gap_percent:
                fvg_info = PatternInfo(
                    pattern_type="FVG",
                    confidence=min(gap_percent / 1.0, 1.0),  # Max confidence at 1%
                    price_level=(candle1['high'] + candle3['low']) / 2,
                    direction="bullish",
                    strength=gap_percent,
                    metadata={
                        'upper_level': candle3['low'],
                        'lower_level': candle1['high'],
                        'gap_size': gap_size,
                        'gap_percent': gap_percent,
                        'candle_idx': current_idx
                    }
                )
                self.active_fvgs.append(fvg_info)
                return True, fvg_info

        # Bearish FVG: Gap zwischen candle1.low und candle3.high
        elif candle1['low'] > candle3['high']:
            gap_size = candle1['low'] - candle3['high']
            gap_percent = gap_size / candle1['low'] * 100

            if gap_percent >= self.min_gap_percent:
                fvg_info = PatternInfo(
                    pattern_type="FVG",
                    confidence=min(gap_percent / 1.0, 1.0),
                    price_level=(candle1['low'] + candle3['high']) / 2,
                    direction="bearish",
                    strength=gap_percent,
                    metadata={
                        'upper_level': candle1['low'],
                        'lower_level': candle3['high'],
                        'gap_size': gap_size,
                        'gap_percent': gap_percent,
                        'candle_idx': current_idx
                    }
                )
                self.active_fvgs.append(fvg_info)
                return True, fvg_info

        return False, None

    def is_price_in_fvg(self, price: float) -> Tuple[bool, Optional[PatternInfo]]:
        """Prüft ob aktueller Preis in einer FVG Zone ist"""
        for fvg in self.active_fvgs:
            upper = fvg.metadata['upper_level']
            lower = fvg.metadata['lower_level']

            if lower <= price <= upper:
                return True, fvg

        return False, None

    def get_nearest_fvg(self, price: float) -> Tuple[float, Optional[PatternInfo]]:
        """Findet nächste FVG und gibt Distanz zurück"""
        if not self.active_fvgs:
            return float('inf'), None

        min_distance = float('inf')
        nearest_fvg = None

        for fvg in self.active_fvgs:
            distance = abs(price - fvg.price_level) / price
            if distance < min_distance:
                min_distance = distance
                nearest_fvg = fvg

        return min_distance, nearest_fvg

    def cleanup_old_fvgs(self, current_price: float, max_age_bars=50):
        """Entfernt alte oder erfüllte FVGs"""
        active_fvgs = []
        for fvg in self.active_fvgs:
            # Prüfe ob FVG noch relevant ist
            if fvg.direction == "bullish" and current_price < fvg.metadata['lower_level']:
                active_fvgs.append(fvg)
            elif fvg.direction == "bearish" and current_price > fvg.metadata['upper_level']:
                active_fvgs.append(fvg)

        self.active_fvgs = active_fvgs


class OrderBlockDetector(PatternDetector):
    """
    Order Block Detector
    Erkennt Bereiche mit hoher Liquidität (Support/Resistance)
    """
    def __init__(self, lookback=20, min_volume_ratio=1.5):
        super().__init__("OrderBlock")
        self.lookback = lookback
        self.min_volume_ratio = min_volume_ratio
        self.support_blocks = []
        self.resistance_blocks = []

    def detect(self, df: pd.DataFrame, current_idx: int) -> Tuple[bool, Optional[PatternInfo]]:
        if current_idx < self.lookback:
            return False, None

        recent_data = df.iloc[current_idx - self.lookback:current_idx + 1]
        current_price = df.iloc[current_idx]['close']

        # Finde potenzielle Order Blocks
        ob_found = False
        ob_info = None

        # Support Order Block: Hohe Volume + Price bounce von Low
        support_candidates = recent_data[
            (recent_data['volume'] > recent_data['volume'].mean() * self.min_volume_ratio) &
            (recent_data['low'] < current_price)
        ]

        if len(support_candidates) > 0:
            strongest_support = support_candidates.loc[support_candidates['volume'].idxmax()]

            ob_info = PatternInfo(
                pattern_type="OrderBlock",
                confidence=min(strongest_support['volume'] / recent_data['volume'].mean() / 2, 1.0),
                price_level=strongest_support['low'],
                direction="support",
                strength=strongest_support['volume'],
                metadata={
                    'type': 'support',
                    'volume': strongest_support['volume'],
                    'price_level': strongest_support['low'],
                    'candle_idx': current_idx
                }
            )
            self.support_blocks.append(ob_info)
            ob_found = True

        # Resistance Order Block: Hohe Volume + Price rejection von High
        resistance_candidates = recent_data[
            (recent_data['volume'] > recent_data['volume'].mean() * self.min_volume_ratio) &
            (recent_data['high'] > current_price)
        ]

        if len(resistance_candidates) > 0 and not ob_found:  # Nur eines pro Kerze
            strongest_resistance = resistance_candidates.loc[resistance_candidates['volume'].idxmax()]

            ob_info = PatternInfo(
                pattern_type="OrderBlock",
                confidence=min(strongest_resistance['volume'] / recent_data['volume'].mean() / 2, 1.0),
                price_level=strongest_resistance['high'],
                direction="resistance",
                strength=strongest_resistance['volume'],
                metadata={
                    'type': 'resistance',
                    'volume': strongest_resistance['volume'],
                    'price_level': strongest_resistance['high'],
                    'candle_idx': current_idx
                }
            )
            self.resistance_blocks.append(ob_info)
            ob_found = True

        return ob_found, ob_info

    def is_near_order_block(self, price: float, tolerance=0.01) -> Dict[str, any]:
        """Prüft Nähe zu Order Blocks"""
        result = {
            'near_support_ob': False,
            'near_resistance_ob': False,
            'support_info': None,
            'resistance_info': None
        }

        # Support Order Blocks
        for ob in self.support_blocks:
            ob_price = ob.metadata['price_level']
            if abs(price - ob_price) / price <= tolerance and price >= ob_price:
                result['near_support_ob'] = True
                result['support_info'] = ob
                break

        # Resistance Order Blocks
        for ob in self.resistance_blocks:
            ob_price = ob.metadata['price_level']
            if abs(price - ob_price) / price <= tolerance and price <= ob_price:
                result['near_resistance_ob'] = True
                result['resistance_info'] = ob
                break

        return result


class LiquidityZoneDetector(PatternDetector):
    """
    Liquidity Zone Detector - wie Trackmania Checkpoint System
    Erkennt Zonen mit hoher Liquidität wo der Preis hingezogen wird
    """
    def __init__(self, volume_threshold=2.0, zone_width=0.005):
        super().__init__("LiquidityZone")
        self.volume_threshold = volume_threshold
        self.zone_width = zone_width  # 0.5% width
        self.liquidity_zones = []

    def detect(self, df: pd.DataFrame, current_idx: int) -> Tuple[bool, Optional[PatternInfo]]:
        if current_idx < 50:  # Brauchen mehr Historie für Volume Profile
            return False, None

        recent_data = df.iloc[current_idx - 50:current_idx + 1]

        # Volume Profile (vereinfacht)
        # Gruppiere Preise in Bins und summiere Volume
        price_min = recent_data['low'].min()
        price_max = recent_data['high'].max()
        num_bins = 20

        price_bins = np.linspace(price_min, price_max, num_bins)
        volume_profile = np.zeros(num_bins - 1)

        for idx, row in recent_data.iterrows():
            # Finde Bin für diese Kerze
            mid_price = (row['high'] + row['low']) / 2
            bin_idx = np.digitize(mid_price, price_bins) - 1
            bin_idx = max(0, min(bin_idx, len(volume_profile) - 1))
            volume_profile[bin_idx] += row['volume']

        # Finde High Volume Nodes (HVN)
        mean_volume = volume_profile.mean()
        high_volume_indices = np.where(volume_profile > mean_volume * self.volume_threshold)[0]

        if len(high_volume_indices) > 0:
            # Stärkste Liquidity Zone
            strongest_idx = high_volume_indices[np.argmax(volume_profile[high_volume_indices])]
            zone_price = (price_bins[strongest_idx] + price_bins[strongest_idx + 1]) / 2
            zone_volume = volume_profile[strongest_idx]

            # Bestimme Richtung zum Zone
            current_price = df.iloc[current_idx]['close']
            direction = 1 if zone_price > current_price else -1

            liquidity_info = PatternInfo(
                pattern_type="LiquidityZone",
                confidence=min(zone_volume / mean_volume / self.volume_threshold, 1.0),
                price_level=zone_price,
                direction="upside" if direction > 0 else "downside",
                strength=zone_volume,
                metadata={
                    'zone_volume': zone_volume,
                    'zone_price': zone_price,
                    'direction': direction,
                    'current_price': current_price,
                    'distance': abs(zone_price - current_price) / current_price
                }
            )

            self.liquidity_zones.append(liquidity_info)
            return True, liquidity_info

        return False, None

    def get_liquidity_direction(self, current_price: float) -> int:
        """Gibt Richtung zur nächsten Liquidity Zone zurück"""
        if not self.liquidity_zones:
            return 0

        nearest_zone = min(self.liquidity_zones,
                          key=lambda z: abs(z.price_level - current_price))

        return 1 if nearest_zone.price_level > current_price else -1


class MarketStructureDetector(PatternDetector):
    """
    Market Structure Detector
    Erkennt Higher Highs/Lower Lows für Trend-Bestimmung
    """
    def __init__(self, swing_lookback=10):
        super().__init__("MarketStructure")
        self.swing_lookback = swing_lookback
        self.structure_history = []

    def detect(self, df: pd.DataFrame, current_idx: int) -> Tuple[bool, Optional[PatternInfo]]:
        if current_idx < self.swing_lookback * 2:
            return False, None

        # Finde Swing Highs und Lows
        highs, lows = self._find_swings(df, current_idx)

        if len(highs) < 2 or len(lows) < 2:
            return False, None

        # Analysiere Market Structure
        structure = self._analyze_structure(highs, lows)

        if structure != "neutral":
            structure_info = PatternInfo(
                pattern_type="MarketStructure",
                confidence=0.7,  # Basis Confidence
                price_level=df.iloc[current_idx]['close'],
                direction=structure,
                strength=1.0,
                metadata={
                    'structure_type': structure,
                    'recent_highs': highs[-2:],
                    'recent_lows': lows[-2:],
                    'trend_strength': self._calculate_trend_strength(highs, lows)
                }
            )
            return True, structure_info

        return False, None

    def _find_swings(self, df: pd.DataFrame, current_idx: int) -> Tuple[List[float], List[float]]:
        """Findet Swing Highs und Lows"""
        data = df.iloc[current_idx - self.swing_lookback * 4:current_idx + 1]

        highs = []
        lows = []

        for i in range(self.swing_lookback, len(data) - self.swing_lookback):
            # Swing High
            if all(data.iloc[i]['high'] >= data.iloc[j]['high']
                  for j in range(i - self.swing_lookback, i + self.swing_lookback + 1) if j != i):
                highs.append(data.iloc[i]['high'])

            # Swing Low
            if all(data.iloc[i]['low'] <= data.iloc[j]['low']
                  for j in range(i - self.swing_lookback, i + self.swing_lookback + 1) if j != i):
                lows.append(data.iloc[i]['low'])

        return highs, lows

    def _analyze_structure(self, highs: List[float], lows: List[float]) -> str:
        """Analysiert Market Structure"""
        if len(highs) >= 2 and len(lows) >= 2:
            # Higher Highs and Higher Lows = Bullish
            if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                return "bullish"
            # Lower Highs and Lower Lows = Bearish
            elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                return "bearish"

        return "neutral"

    def _calculate_trend_strength(self, highs: List[float], lows: List[float]) -> float:
        """Berechnet Trend-Stärke"""
        if len(highs) < 2 or len(lows) < 2:
            return 0.0

        high_momentum = abs(highs[-1] - highs[-2]) / highs[-2]
        low_momentum = abs(lows[-1] - lows[-2]) / lows[-2]

        return (high_momentum + low_momentum) / 2


class PatternManager:
    """
    Verwaltet alle Pattern Detectors
    """
    def __init__(self):
        self.detectors = {}
        self.pattern_history = []

    def add_detector(self, detector: PatternDetector):
        """Fügt einen Pattern Detector hinzu"""
        self.detectors[detector.name] = detector

    def detect_all_patterns(self, df: pd.DataFrame, current_idx: int) -> Dict[str, PatternInfo]:
        """Führt alle Pattern Detections aus"""
        detected_patterns = {}

        for name, detector in self.detectors.items():
            found, pattern_info = detector.detect(df, current_idx)
            if found and pattern_info:
                detected_patterns[name] = pattern_info

        # Speichere für Historie
        self.pattern_history.append({
            'idx': current_idx,
            'patterns': detected_patterns,
            'price': df.iloc[current_idx]['close']
        })

        return detected_patterns

    def get_trading_signals(self, df: pd.DataFrame, current_idx: int) -> Dict[str, any]:
        """
        Generiert Trading Signals basierend auf allen Patterns
        """
        current_price = df.iloc[current_idx]['close']
        signals = {
            'in_fvg_zone': False,
            'fvg_distance': float('inf'),
            'near_support_ob': False,
            'near_resistance_ob': False,
            'liquidity_direction': 0,
            'market_structure': 0,
            'pattern_confluence': 0
        }

        # FVG Signals
        if 'FVG' in self.detectors:
            fvg_detector = self.detectors['FVG']
            in_fvg, fvg_info = fvg_detector.is_price_in_fvg(current_price)
            distance, _ = fvg_detector.get_nearest_fvg(current_price)

            signals['in_fvg_zone'] = in_fvg
            signals['fvg_distance'] = distance

        # Order Block Signals
        if 'OrderBlock' in self.detectors:
            ob_detector = self.detectors['OrderBlock']
            ob_signals = ob_detector.is_near_order_block(current_price)
            signals.update(ob_signals)

        # Liquidity Zone Signals
        if 'LiquidityZone' in self.detectors:
            lz_detector = self.detectors['LiquidityZone']
            signals['liquidity_direction'] = lz_detector.get_liquidity_direction(current_price)

        # Market Structure
        if 'MarketStructure' in self.detectors:
            ms_detector = self.detectors['MarketStructure']
            if ms_detector.structure_history:
                last_structure = ms_detector.structure_history[-1]
                if last_structure.direction == "bullish":
                    signals['market_structure'] = 1
                elif last_structure.direction == "bearish":
                    signals['market_structure'] = -1

        # Pattern Confluence (Anzahl bestätigender Signale)
        confluence = 0
        if signals['in_fvg_zone']:
            confluence += 1
        if signals['near_support_ob'] or signals['near_resistance_ob']:
            confluence += 1
        if signals['liquidity_direction'] != 0:
            confluence += 1

        signals['pattern_confluence'] = confluence

        return signals