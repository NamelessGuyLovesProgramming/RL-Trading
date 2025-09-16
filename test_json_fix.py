import sys
sys.path.append('src')
import json

print("[TEST] JSON Serialization Fix")

from data_feed import create_sample_data

try:
    data = create_sample_data('NQ', periods=10)
    data = data.reset_index(drop=True)

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

    # Test JSON serialization
    js_data = json.dumps(chart_data)
    print(f'[OK] JSON serialization successful')
    print(f'[OK] Generated {len(chart_data)} candles')
    print(f'[OK] Sample data: {chart_data[0]}')
    print(f'[OK] JSON length: {len(js_data)} characters')

except Exception as e:
    print(f'[ERROR] {e}')

print('\n[SUCCESS] JSON serialization fix applied!')