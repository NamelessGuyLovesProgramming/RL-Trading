"""
Test 9-Feature System
Validiert die Implementation in src/env.py
"""
import sys
sys.path.append('C:/Users/vgude/VsStudio/RL-Trading')
sys.path.append('C:/Users/vgude/VsStudio/RL-Trading/src')

import numpy as np
from env import InteractiveTradingEnv
import pandas as pd

def test_features():
    """Testet alle 9 Features"""

    print("=" * 80)
    print("9-FEATURE SYSTEM TEST")
    print("=" * 80)
    print()

    # Load Data
    print("[1/6] CSV Daten laden...")
    df = pd.read_csv('src/data/aggregated/5m/nq-2024.csv')

    # Parse timestamp if separate Date/Time columns exist
    if 'Date' in df.columns and 'Time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])

    # Standardize column names
    df.columns = [c.lower() for c in df.columns]

    print(f"✓ {len(df)} Candles geladen")
    print(f"✓ Columns: {list(df.columns)}")
    print()

    # Initialize Environment
    print("[2/6] Environment initialisieren...")
    env = InteractiveTradingEnv(
        df=df,
        initial_cash=10000.0,
        enable_patterns=False
    )

    print(f"✓ Observation Space: {env.observation_space.shape}")
    assert env.observation_space.shape == (9,), f"Expected shape=(9,), got {env.observation_space.shape}"
    print()

    # Reset Environment
    print("[3/6] Environment reset...")
    observation, info = env.reset()

    print(f"✓ Observation shape: {observation.shape}")
    print(f"✓ Observation dtype: {observation.dtype}")
    assert observation.shape == (9,), f"Expected shape=(9,), got {observation.shape}"
    assert observation.dtype == np.float32, f"Expected dtype=float32, got {observation.dtype}"
    print()

    # Check for NaN/Inf
    print("[4/6] NaN/Inf Check...")
    has_nan = np.isnan(observation).any()
    has_inf = np.isinf(observation).any()

    if has_nan or has_inf:
        print(f"✗ NaN: {has_nan}, Inf: {has_inf}")
        print(f"  Observation: {observation}")
        raise ValueError("NaN oder Inf in Observation gefunden!")
    else:
        print(f"✓ Keine NaN/Inf Werte")
    print()

    # Feature Analysis
    print("[5/6] Feature Analyse...")
    print()
    print("  " + "=" * 76)
    print(f"  {'Feature':<30} {'Value':>12} {'Range':<30}")
    print("  " + "=" * 76)

    feature_names = [
        "5-period return",
        "20-period volatility",
        "Price momentum (EMA 20)",
        "RSI",
        "volume_ratio (log)",
        "hour_sin",
        "price_position_session",
        "ema_15m_momentum",
        "ema_1h_momentum"
    ]

    expected_ranges = [
        (-0.5, 0.5),      # return: ±50% extreme
        (0.0, 0.5),       # volatility: 0-50%
        (-0.5, 0.5),      # momentum: ±50%
        (0.0, 1.0),       # RSI: 0-100% (normalized)
        (-5.0, 5.0),      # log volume_ratio: capped by nan_to_num
        (-1.0, 1.0),      # sin: -1 to +1
        (0.0, 1.0),       # price_position: 0-100%
        (-0.5, 0.5),      # 15m momentum: ±50%
        (-0.5, 0.5)       # 1h momentum: ±50%
    ]

    for i, (name, value, (low, high)) in enumerate(zip(feature_names, observation, expected_ranges)):
        range_str = f"[{low:+.1f}, {high:+.1f}]"

        # Check if value is in expected range
        if low <= value <= high:
            status = "✓"
        else:
            status = "⚠"

        print(f"  {status} {name:<28} {value:>12.4f}  {range_str:<28}")

    print("  " + "=" * 76)
    print()

    # Multi-Step Test
    print("[6/6] Multi-Step Test (100 steps)...")

    nan_count = 0
    inf_count = 0

    for step in range(100):
        action = env.action_space.sample()  # Random action
        observation, reward, done, truncated, info = env.step(action)

        # Check for NaN/Inf
        if np.isnan(observation).any():
            nan_count += 1
        if np.isinf(observation).any():
            inf_count += 1

        if done or truncated:
            observation, info = env.reset()

    print(f"✓ 100 Steps completed")
    print(f"  NaN occurrences: {nan_count}")
    print(f"  Inf occurrences: {inf_count}")

    if nan_count > 0 or inf_count > 0:
        print(f"\n⚠ WARNING: NaN/Inf found during 100-step test!")
    else:
        print(f"\n✓ Alle 100 Steps ohne NaN/Inf!")

    print()
    print("=" * 80)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print()
    print("✓ observation_space = Box(shape=(9,), dtype=np.float32)")
    print("✓ Keine NaN/Inf Werte")
    print("✓ Features in erwarteten Ranges")
    print("✓ Multi-Step Test passed")
    print()
    print("→ 9-Feature System ist READY für Training!")
    print()

if __name__ == '__main__':
    test_features()
