#!/usr/bin/env python3
"""
Chart-Only Application
Minimalistische Trading Chart App nur mit Chart und Position Tool
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.components.chart import create_trading_chart

# Streamlit Page Config
st.set_page_config(
    page_title="RL Trading Chart",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS für vollständige Chart-Darstellung
st.markdown("""
<style>
    .main > div {
        padding-top: 0rem;
        padding-bottom: 0rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    .stApp > header {
        background-color: transparent;
    }
    .stApp {
        margin-top: -80px;
    }
    [data-testid="stHeader"] {
        display: none;
    }
    [data-testid="stToolbar"] {
        display: none;
    }
    .stDeployButton {
        display: none;
    }
    footer {
        display: none;
    }
    .viewerBadge_container__1QSob {
        display: none;
    }
    #MainMenu {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

def generate_sample_data():
    """Generiert Sample Trading-Daten für den Chart"""

    # Zeitraum: Letzte 100 Tage
    end_date = datetime.now()
    start_date = end_date - timedelta(days=100)

    # 5-Minuten Kerzen generieren
    time_range = pd.date_range(start=start_date, end=end_date, freq='5min')

    # Realistische NQ Futures Preise
    base_price = 19000
    prices = []
    current_price = base_price

    for i in range(len(time_range)):
        # Zufällige Preisbewegung
        change = np.random.normal(0, 10)  # Mean=0, StdDev=10 Punkte
        current_price += change

        # OHLC für diese Kerze
        open_price = current_price
        high_price = open_price + abs(np.random.normal(0, 5))
        low_price = open_price - abs(np.random.normal(0, 5))
        close_price = open_price + np.random.normal(0, 3)

        # Volume
        volume = np.random.randint(100, 1000)

        prices.append({
            'Open': open_price,
            'High': max(open_price, high_price, close_price),
            'Low': min(open_price, low_price, close_price),
            'Close': close_price,
            'Volume': volume
        })

        current_price = close_price

    # DataFrame erstellen
    df = pd.DataFrame(prices, index=time_range)

    return df

def main():
    """Hauptfunktion der Chart-Only App"""

    # Sample Daten generieren
    df = generate_sample_data()

    # Data Dictionary für Chart-Komponente
    data_dict = {
        'data': df,
        'symbol': 'NQ=F',
        'interval': '5m'
    }

    # Chart erstellen und anzeigen
    chart_html = create_trading_chart(
        data_dict=data_dict,
        trades=None,
        show_volume=True,
        show_ma20=False,
        show_ma50=False,
        show_bollinger=False,
        selected_symbol="NQ=F",
        selected_interval="5m"
    )

    # Chart HTML direkt anzeigen
    st.components.v1.html(chart_html, height=800, scrolling=False)

if __name__ == "__main__":
    main()