import streamlit as st
import sys
import pandas as pd
import json

# Add src to path for imports
sys.path.append('src')

from data_feed import create_sample_data

st.set_page_config(
    page_title="Debug TradingView Chart",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 Debug TradingView Chart")

# Test data generation
st.header("1. Testing Data Generation")

try:
    data = create_sample_data('NQ', periods=100)
    st.success(f"✅ Generated {len(data)} candles")
    st.write("Sample data:")
    st.dataframe(data.head())

    # Convert to chart format
    data = data.reset_index(drop=True)
    chart_data = []

    for idx in range(min(50, len(data))):  # Only first 50 for testing
        row = data.iloc[idx]
        chart_data.append({
            'time': idx,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 1000))
        })

    st.success(f"✅ Converted to {len(chart_data)} chart candles")
    st.write("Chart data sample:")
    st.json(chart_data[:3])

    # Test JSON serialization
    js_data = json.dumps(chart_data)
    st.success(f"✅ JSON serialization successful ({len(js_data)} chars)")

except Exception as e:
    st.error(f"❌ Data generation failed: {e}")
    chart_data = []

# Simple chart test
st.header("2. Testing Simple Chart")

if chart_data:
    # Create a minimal working chart
    chart_html = f"""
    <div id="chart_container" style="height: 400px; background: #131722; border: 1px solid #333;"></div>

    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script>
    try {{
        console.log('Starting chart creation...');

        const container = document.getElementById('chart_container');
        if (!container) {{
            console.error('Container not found!');
        }}

        const chart = LightweightCharts.createChart(container, {{
            width: container.offsetWidth,
            height: 400,
            layout: {{
                background: {{ color: '#131722' }},
                textColor: '#d9d9d9',
            }},
            grid: {{
                vertLines: {{ color: '#2B2B43' }},
                horzLines: {{ color: '#2B2B43' }},
            }},
            timeScale: {{
                timeVisible: false,
                secondsVisible: false,
            }},
        }});

        console.log('Chart created, adding series...');

        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        }});

        const data = {js_data};
        console.log('Data loaded:', data.length, 'candles');
        console.log('First candle:', data[0]);

        candleSeries.setData(data);

        console.log('Chart data set successfully!');

        chart.timeScale().fitContent();

        // Add debug info
        const debugDiv = document.createElement('div');
        debugDiv.style.color = 'white';
        debugDiv.style.padding = '10px';
        debugDiv.innerHTML = `
            <strong>Debug Info:</strong><br>
            - Chart library loaded: ✅<br>
            - Data points: ${{data.length}}<br>
            - Price range: $${{Math.min(...data.map(d => d.low)).toFixed(2)}} - $${{Math.max(...data.map(d => d.high)).toFixed(2)}}<br>
            - Time range: ${{data[0].time}} - ${{data[data.length-1].time}}
        `;
        container.appendChild(debugDiv);

    }} catch (error) {{
        console.error('Chart creation failed:', error);
        document.getElementById('chart_container').innerHTML = `
            <div style="color: red; padding: 20px;">
                <strong>Chart Error:</strong><br>
                ${{error.message}}<br><br>
                <strong>Check browser console for details.</strong>
            </div>
        `;
    }}
    </script>
    """

    st.components.v1.html(chart_html, height=500)

else:
    st.error("No chart data available")

# Alternative: Plotly chart as backup
st.header("3. Backup Plotly Chart")

if chart_data:
    import plotly.graph_objects as go

    df_chart = pd.DataFrame(chart_data)

    fig = go.Figure(data=go.Candlestick(
        x=df_chart['time'],
        open=df_chart['open'],
        high=df_chart['high'],
        low=df_chart['low'],
        close=df_chart['close']
    ))

    fig.update_layout(
        title="Backup Plotly Chart",
        xaxis_title="Time",
        yaxis_title="Price",
        template="plotly_dark"
    )

    st.plotly_chart(fig, use_container_width=True)

# Debug info
st.header("4. Debug Information")
st.write(f"Python version: {sys.version}")
st.write(f"Streamlit version: {st.__version__}")
st.write("Check browser console for JavaScript errors")

# Instructions
st.header("5. Troubleshooting")
st.write("""
**If the chart is empty:**
1. Check browser console (F12 → Console tab)
2. Look for JavaScript errors
3. Verify Lightweight Charts library loads
4. Check data format and content
5. Try the backup Plotly chart above

**Common issues:**
- External script blocked by security settings
- Data format incompatible with Lightweight Charts
- Container size/visibility problems
""")