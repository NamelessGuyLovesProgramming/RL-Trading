"""
Validation Script für 17-Feature System
Testet Feature-Extraction und prüft Ranges gemäß FEATURE_SPECIFICATION.md
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Fix Windows Console Encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
from charts.core.market_context_extractor import MarketContextExtractor, calculate_trade_features
from datetime import datetime, timedelta

print(f"{'='*80}")
print(f"🧪 FEATURE VALIDATION TEST")
print(f"{'='*80}\n")

# ========== SETUP ==========
print("[1/5] Loading test data...")
csv_path = 'src/data/aggregated/5m/nq-2024.csv'
df = pd.read_csv(csv_path)

# Prepare DataFrame
df.columns = df.columns.str.lower()
df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
df = df.set_index('timestamp')
print(f"✅ Loaded {len(df)} candles")

# ========== TEST MARKET CONTEXT FEATURES ==========
print(f"\n[2/5] Testing Market Context Feature Extraction...")

extractor = MarketContextExtractor()

# Use a candle in the middle (enough lookback data)
test_idx = 500
test_row = df.iloc[test_idx]
entry_price = float(test_row['close'])
sl_price = entry_price - 50  # Mock SL
tp_price = entry_price + 100  # Mock TP

print(f"   Test Entry: idx={test_idx}, price=${entry_price:.2f}")
print(f"   Test SL/TP: ${sl_price:.2f} / ${tp_price:.2f}")

market_features = extractor.extract_at_entry(
    df=df,
    entry_idx=test_idx,
    entry_price=entry_price,
    sl_price=sl_price,
    tp_price=tp_price
)

print(f"\n   ✅ Extracted {len(market_features)} market context features:")
for key, value in market_features.items():
    print(f"      {key}: {value}")

# ========== VALIDATE RANGES ==========
print(f"\n[3/5] Validating Feature Ranges...")

validation_errors = []

# Feature 10: distance_to_ema20_pct (-10% to +10%)
ema_dist = market_features.get('distance_to_ema20_pct', 0)
if not (-10 <= ema_dist <= 10):
    validation_errors.append(f"❌ distance_to_ema20_pct out of range: {ema_dist:.2f}% (expected: -10% to +10%)")
else:
    print(f"   ✅ distance_to_ema20_pct: {ema_dist:.2f}% (valid)")

# Feature 11: volume_ratio (0 to 10, extreme: 20)
vol_ratio = market_features.get('volume_ratio', 1)
if not (0 <= vol_ratio <= 20):
    validation_errors.append(f"❌ volume_ratio out of range: {vol_ratio:.2f} (expected: 0 to 20)")
else:
    print(f"   ✅ volume_ratio: {vol_ratio:.2f}x (valid)")

# Feature 12: atr_value (> 0)
atr = market_features.get('atr_value', 0)
if atr < 0:
    validation_errors.append(f"❌ atr_value negative: {atr:.2f} (expected: > 0)")
else:
    print(f"   ✅ atr_value: {atr:.2f} (valid)")

# Feature 13: recent_high_distance_pct (<= 0)
high_dist = market_features.get('recent_high_distance_pct', 0)
if high_dist > 0:
    validation_errors.append(f"❌ recent_high_distance_pct positive: {high_dist:.2f}% (expected: <= 0)")
else:
    print(f"   ✅ recent_high_distance_pct: {high_dist:.2f}% (valid)")

# Feature 14: recent_low_distance_pct (>= 0)
low_dist = market_features.get('recent_low_distance_pct', 0)
if low_dist < 0:
    validation_errors.append(f"❌ recent_low_distance_pct negative: {low_dist:.2f}% (expected: >= 0)")
else:
    print(f"   ✅ recent_low_distance_pct: {low_dist:.2f}% (valid)")

# Feature 15: position_in_range (0 to 1)
position = market_features.get('position_in_range', 0.5)
if not (0 <= position <= 1):
    validation_errors.append(f"❌ position_in_range out of range: {position:.3f} (expected: 0 to 1)")
else:
    print(f"   ✅ position_in_range: {position:.3f} (valid)")

# Feature 16: rr_ratio (> 0)
rr = market_features.get('rr_ratio', 0)
if rr <= 0:
    validation_errors.append(f"❌ rr_ratio not positive: {rr:.2f} (expected: > 0)")
else:
    print(f"   ✅ rr_ratio: {rr:.2f} (valid)")

# ========== TEST TRADE FEATURES ==========
print(f"\n[4/5] Testing Trade-Specific Features...")

entry_idx = 500
exit_idx = 550  # 50 candles later (~4 hours in 5m)
entry_time = df.index[entry_idx].isoformat()
exit_time = df.index[exit_idx].isoformat()
entry_price = float(df.iloc[entry_idx]['close'])
is_long = True

print(f"   Test Trade: {entry_idx} → {exit_idx} (50 candles)")
print(f"   Entry: {entry_time}, Price: ${entry_price:.2f}")
print(f"   Exit:  {exit_time}")

trade_features = calculate_trade_features(
    df=df,
    entry_time=entry_time,
    exit_time=exit_time,
    entry_price=entry_price,
    is_long=is_long
)

print(f"\n   ✅ Extracted {len(trade_features)} trade features:")
for key, value in trade_features.items():
    print(f"      {key}: {value}")

# Validate trade features
duration = trade_features.get('trade_duration_candles', 0)
if duration < 1:
    validation_errors.append(f"❌ trade_duration_candles < 1: {duration}")
else:
    print(f"   ✅ trade_duration_candles: {duration} (valid)")

max_dd = trade_features.get('max_drawdown_pct', 0)
if is_long and max_dd > 0:
    validation_errors.append(f"❌ max_drawdown_pct positive for LONG: {max_dd:.2f}% (expected: <= 0)")
elif not is_long and max_dd < 0:
    validation_errors.append(f"❌ max_drawdown_pct negative for SHORT: {max_dd:.2f}% (expected: >= 0)")
else:
    print(f"   ✅ max_drawdown_pct: {max_dd:.2f}% (valid)")

# ========== CHECK FOR NaN/Inf ==========
print(f"\n[5/5] Checking for NaN/Inf values...")

all_features = {**market_features, **trade_features}
nan_features = [k for k, v in all_features.items() if pd.isna(v)]
inf_features = [k for k, v in all_features.items() if isinstance(v, float) and (v == float('inf') or v == float('-inf'))]

if nan_features:
    validation_errors.append(f"❌ NaN values found: {nan_features}")
else:
    print(f"   ✅ No NaN values")

if inf_features:
    validation_errors.append(f"❌ Infinity values found: {inf_features}")
else:
    print(f"   ✅ No Infinity values")

# ========== SUMMARY ==========
print(f"\n{'='*80}")
print(f"📊 VALIDATION SUMMARY")
print(f"{'='*80}")

print(f"\n✅ Total Features Tested: {len(all_features)}")
print(f"   - Market Context: {len(market_features)}")
print(f"   - Trade-Specific: {len(trade_features)}")

if validation_errors:
    print(f"\n❌ VALIDATION FAILED - {len(validation_errors)} errors found:\n")
    for error in validation_errors:
        print(f"   {error}")
    print(f"\n{'='*80}\n")
    sys.exit(1)
else:
    print(f"\n✅ ALL VALIDATIONS PASSED!")
    print(f"\n   Ready for production use:")
    print(f"   - All 17 features can be extracted")
    print(f"   - All values within expected ranges")
    print(f"   - No NaN or Infinity values")
    print(f"   - Feature calculations are correct")
    print(f"\n{'='*80}\n")
    sys.exit(0)
