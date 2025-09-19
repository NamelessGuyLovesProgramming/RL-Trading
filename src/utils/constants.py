"""
Asset-Definitionen und Konstanten
Verfügbare Trading Assets nach Kategorien organisiert
"""

# Available Assets Configuration - erweitert und strukturiert
AVAILABLE_ASSETS = {
    "futures": [
        {"symbol": "NQ=F", "name": "NASDAQ-100 Futures", "description": "E-mini NASDAQ-100 Index Futures"},
        {"symbol": "ES=F", "name": "S&P 500 Futures", "description": "E-mini S&P 500 Index Futures"},
        {"symbol": "YM=F", "name": "Dow Jones Futures", "description": "E-mini Dow Jones Industrial Average Futures"},
        {"symbol": "RTY=F", "name": "Russell 2000 Futures", "description": "E-mini Russell 2000 Index Futures"},
        {"symbol": "GC=F", "name": "Gold Futures", "description": "Gold Continuous Contract"},
        {"symbol": "CL=F", "name": "Crude Oil Futures", "description": "Crude Oil Continuous Contract"},
    ],
    "stocks": [
        {"symbol": "AAPL", "name": "Apple Inc.", "description": "Technology - Consumer Electronics"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "description": "Technology - Software"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "description": "Technology - Internet Services"},
        {"symbol": "TSLA", "name": "Tesla Inc.", "description": "Automotive - Electric Vehicles"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "description": "Consumer Discretionary - E-commerce"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "description": "Technology - Semiconductors"},
        {"symbol": "META", "name": "Meta Platforms Inc.", "description": "Technology - Social Media"},
        {"symbol": "NFLX", "name": "Netflix Inc.", "description": "Entertainment - Streaming"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "description": "Technology - Semiconductors"},
        {"symbol": "CRM", "name": "Salesforce Inc.", "description": "Technology - Cloud Software"},
        {"symbol": "INTC", "name": "Intel Corporation", "description": "Technology - Semiconductors"},
        {"symbol": "BABA", "name": "Alibaba Group", "description": "Technology - E-commerce China"},
        {"symbol": "PYPL", "name": "PayPal Holdings", "description": "Financial - Digital Payments"},
        {"symbol": "DIS", "name": "The Walt Disney Company", "description": "Entertainment - Media"},
        {"symbol": "V", "name": "Visa Inc.", "description": "Financial - Payment Networks"},
        {"symbol": "MA", "name": "Mastercard Inc.", "description": "Financial - Payment Networks"}
    ],
    "crypto": [
        {"symbol": "BTC-USD", "name": "Bitcoin", "description": "Cryptocurrency - Digital Gold"},
        {"symbol": "ETH-USD", "name": "Ethereum", "description": "Cryptocurrency - Smart Contracts"},
        {"symbol": "ADA-USD", "name": "Cardano", "description": "Cryptocurrency - Proof of Stake"},
        {"symbol": "DOT-USD", "name": "Polkadot", "description": "Cryptocurrency - Interoperability"},
        {"symbol": "LINK-USD", "name": "Chainlink", "description": "Cryptocurrency - Oracle Network"},
        {"symbol": "LTC-USD", "name": "Litecoin", "description": "Cryptocurrency - Digital Silver"}
    ],
    "forex": [
        {"symbol": "EURUSD=X", "name": "EUR/USD", "description": "Euro vs US Dollar"},
        {"symbol": "GBPUSD=X", "name": "GBP/USD", "description": "British Pound vs US Dollar"},
        {"symbol": "USDJPY=X", "name": "USD/JPY", "description": "US Dollar vs Japanese Yen"},
        {"symbol": "USDCHF=X", "name": "USD/CHF", "description": "US Dollar vs Swiss Franc"}
    ],
    "indices": [
        {"symbol": "^GSPC", "name": "S&P 500", "description": "US Large Cap Index"},
        {"symbol": "^IXIC", "name": "NASDAQ Composite", "description": "US Tech Index"},
        {"symbol": "^DJI", "name": "Dow Jones Industrial", "description": "US Blue Chip Index"},
        {"symbol": "^RUT", "name": "Russell 2000", "description": "US Small Cap Index"}
    ]
}

def validate_symbol(symbol):
    """Prüft ob Symbol in verfügbaren Assets existiert"""
    for category in AVAILABLE_ASSETS.values():
        for asset in category:
            if asset["symbol"] == symbol:
                return True
    return False

def get_asset_info(symbol):
    """Gibt Asset-Informationen für ein Symbol zurück"""
    for category in AVAILABLE_ASSETS.values():
        for asset in category:
            if asset["symbol"] == symbol:
                return asset
    return None

def get_all_symbols():
    """Gibt alle verfügbaren Symbole als Liste zurück"""
    symbols = []
    for category in AVAILABLE_ASSETS.values():
        for asset in category:
            symbols.append(asset["symbol"])
    return symbols

def get_symbols_by_category(category):
    """Gibt Symbole einer bestimmten Kategorie zurück"""
    if category in AVAILABLE_ASSETS:
        return [asset["symbol"] for asset in AVAILABLE_ASSETS[category]]
    return []