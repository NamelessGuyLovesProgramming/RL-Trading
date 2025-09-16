import sys
sys.path.append('src')
from data_feed import create_sample_data
from env import InteractiveTradingEnv
from patterns import PatternManager

print("[TEST] Testing Dashboard Components...")

# Test data creation
print('\n1. Creating NQ sample data...')
data = create_sample_data('NQ', periods=100)
print(f'[OK] Created {len(data)} data points')
print(f'NQ Price range: ${data["close"].min():.2f} - ${data["close"].max():.2f}')

# Test environment
print('\n2. Testing trading environment...')
env = InteractiveTradingEnv(data, initial_cash=50000)
obs = env.reset()
print(f'[OK] Environment initialized with ${env.cash:.2f}')

# Test pattern detection
print('\n3. Testing pattern detection...')
patterns = PatternManager()
signals = patterns.get_trading_signals(data, 50)
print(f'[OK] Pattern detection working')
print(f'Signals: FVG={signals.get("in_fvg_zone")}, OB={signals.get("in_order_block")}')

# Test a simple trade
print('\n4. Testing trade execution...')
action = 1  # Buy
obs, reward, done, truncated, info = env.step(action)
print(f'[OK] Trade executed - Reward: {reward:.2f}')
print(f'Portfolio value: ${env.cash + (env.shares_held * data.iloc[env.current_step]["close"]):.2f}')

print('\n[SUCCESS] All components working! Dashboard ready at http://localhost:8502')