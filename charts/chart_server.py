"""
FastAPI Chart Server - COMPLETE REFACTOR Entry Point
Vollständig funktionsfähiger Server mit Dependency Injection

REFACTOR PHASE 5: Sauberer Startup mit allen Features
"""

# -*- coding: utf-8 -*-
import sys
import os

# Windows UTF-8 encoding fix
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from datetime import datetime
import logging

# Pfad-Setup
parent_dir = os.path.dirname(os.path.dirname(__file__))
charts_dir = os.path.dirname(__file__)
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, 'src'))

# Core Imports
from charts.core import (
    UnifiedStateManager,
    ChartDataValidator,
    ChartDataCache,
    ChartSeriesLifecycleManager,
    DebugController,
    UnifiedTimeManager,
    UnifiedPriceRepository,
    TimeframeDataRepository,
    CSVLoader,
    ConnectionManager,
    UniversalSkipRenderer
)

# Services Imports
from charts.services import (
    ChartService,
    TimeframeService,
    NavigationService,
    DebugService,
    PositionService,
    AccountService
)

# Router imports
from charts.routes import chart as chart_routes
from charts.routes import debug as debug_routes
from charts.routes import account as account_routes
from charts.routes import static as static_routes
from charts.routes.websocket_handler import handle_websocket_commands

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== FastAPI App =====
app = FastAPI(
    title="RL Trading Chart Server 2.0",
    version="2.0.0",
    description="Modular Chart Server mit Clean Architecture"
)

# ===== Global State & Components (Legacy Compatibility) =====
# Diese globals werden benötigt für Router-Setup-Functions
manager: ConnectionManager = None
unified_state: UnifiedStateManager = None
unified_time_manager: UnifiedTimeManager = None
debug_controller: DebugController = None
chart_lifecycle_manager: ChartSeriesLifecycleManager = None
data_validator: ChartDataValidator = None
price_repository: UnifiedPriceRepository = None
timeframe_data_repository: TimeframeDataRepository = None
universal_renderer: UniversalSkipRenderer = None

# Services
chart_service: ChartService = None
timeframe_service: TimeframeService = None
navigation_service: NavigationService = None
debug_service: DebugService = None
position_service: PositionService = None
account_service: AccountService = None

# Global Data
initial_chart_data = []
global_skip_events = []
debug_control_timeframe = "5m"

# DataIntegrityGuard Class (inline da nicht in core/)
class DataIntegrityGuard:
    """BULLETPROOF Data Validation - garantiert nie null/undefined"""

    @staticmethod
    def sanitize_chart_data(data, source="unknown"):
        """Bereinigt Chart-Daten von null/undefined Werten"""
        if not isinstance(data, list):
            logger.warning(f"[DATA-GUARD] Invalid data type from {source}: {type(data)}")
            return []

        validated_data = []
        for i, candle in enumerate(data):
            if DataIntegrityGuard._validate_candle(candle):
                safe_candle = {
                    'time': int(float(candle['time'])),
                    'open': float(candle['open']),
                    'high': float(candle['high']),
                    'low': float(candle['low']),
                    'close': float(candle['close'])
                }
                if 'volume' in candle and candle['volume'] is not None:
                    try:
                        safe_candle['volume'] = int(float(candle['volume']))
                    except:
                        safe_candle['volume'] = 0
                validated_data.append(safe_candle)

        if not validated_data and data:
            logger.warning(f"[DATA-GUARD] All candles filtered from {source}")
            import time
            validated_data = [{
                'time': int(time.time()),
                'open': 20000.0,
                'high': 20010.0,
                'low': 19990.0,
                'close': 20005.0,
                'volume': 100
            }]

        return validated_data

    @staticmethod
    def _validate_candle(candle):
        """Validiert einzelne Kerze"""
        if not candle or not isinstance(candle, dict):
            return False

        required_fields = ['time', 'open', 'high', 'low', 'close']
        for field in required_fields:
            if field not in candle or candle[field] is None:
                return False

        try:
            time_val = int(float(candle['time']))
            open_val = float(candle['open'])
            high_val = float(candle['high'])
            low_val = float(candle['low'])
            close_val = float(candle['close'])

            if time_val <= 0:
                return False
            if any(v <= 0 for v in [open_val, high_val, low_val, close_val]):
                return False
            if high_val < max(open_val, close_val, low_val):
                return False
            if low_val > min(open_val, close_val, high_val):
                return False

            return True
        except (ValueError, TypeError, KeyError):
            return False


def initialize_components():
    """Initialisiert alle Komponenten beim Server-Start"""
    global manager, unified_state, unified_time_manager, debug_controller
    global chart_lifecycle_manager, data_validator, price_repository
    global timeframe_data_repository, universal_renderer
    global chart_service, timeframe_service, navigation_service, debug_service, position_service, account_service
    global initial_chart_data, global_skip_events, debug_control_timeframe

    logger.info("=" * 60)
    logger.info("🚀 Initializing Chart Server Components...")
    logger.info("=" * 60)

    # Step 1: Load Initial Chart Data
    logger.info("[INIT] Loading initial chart data...")
    csv_loader = CSVLoader()

    # Lade initiale 5m Chart-Daten aus CSV (wie chart_server.py Line 714-747)
    try:
        import pandas as pd
        from pathlib import Path

        csv_path = Path("src/data/aggregated/5m/nq-2024.csv")
        if csv_path.exists():
            logger.info(f"[INIT] CSV gefunden: {csv_path}")

            # Lade ausreichend Kerzen für funktionsfähigen Chart
            df = pd.read_csv(csv_path).tail(300)  # 300 Kerzen für stabilen Chart
            logger.info(f"[INIT] CSV gelesen: {len(df)} Zeilen")

            # Konvertiere zu Chart-Format
            initial_chart_data.clear()
            for _, row in df.iterrows():
                dt_str = f"{row['Date']} {row['Time']}"
                dt = pd.to_datetime(dt_str, format='mixed', dayfirst=True)

                initial_chart_data.append({
                    'time': int(dt.timestamp()),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']) if 'Volume' in row else 0
                })

            logger.info(f"[INIT] Initial chart data loaded: {len(initial_chart_data)} candles")
        else:
            logger.warning(f"[INIT] CSV not found: {csv_path} - starting with empty chart")
            initial_chart_data.clear()
    except Exception as e:
        logger.error(f"[INIT] Error loading initial chart data: {e}")
        initial_chart_data.clear()

    # Step 2: Core Components
    logger.info("[INIT] Creating core components...")
    unified_state = UnifiedStateManager()
    unified_time_manager = UnifiedTimeManager()
    chart_lifecycle_manager = ChartSeriesLifecycleManager()
    data_validator = ChartDataValidator()
    price_repository = UnifiedPriceRepository()

    # Initialize global time
    if initial_chart_data:
        last_candle_time = initial_chart_data[-1]['time']
        unified_time_manager.initialize_time(last_candle_time)
        logger.info(f"[INIT] Global time initialized: {datetime.fromtimestamp(last_candle_time)}")

    # Step 3: WebSocket Manager
    logger.info("[INIT] Creating WebSocket manager...")
    manager = ConnectionManager()
    manager.chart_state = {
        'data': initial_chart_data,
        'interval': '5m',
        'symbol': 'NQ=F',
        'positions': []
    }

    # Step 4: Debug Controller & Dependencies
    logger.info("[INIT] Creating debug controller...")
    timeframe_data_repository = TimeframeDataRepository(csv_loader, unified_time_manager)

    debug_controller = DebugController(
        unified_time_manager=unified_time_manager,
        csv_loader=csv_loader,
        initial_chart_data=initial_chart_data,
        unified_state=unified_state
    )

    # Step 5: Universal Skip Renderer
    logger.info("[INIT] Creating skip renderer...")
    universal_renderer = UniversalSkipRenderer()  # No parameters needed

    # Step 6: Services Layer
    logger.info("[INIT] Creating services...")

    chart_service = ChartService(
        price_repo=price_repository,
        timeframe_repo=timeframe_data_repository,
        cache_manager=ChartDataCache(),
        validator=data_validator,
        unified_time_manager=unified_time_manager
    )

    timeframe_service = TimeframeService(
        timeframe_repo=timeframe_data_repository,
        sync_manager=debug_controller.sync_manager,
        aggregator=debug_controller.aggregator,
        series_lifecycle=chart_lifecycle_manager,
        unified_time_manager=unified_time_manager,
        validator=data_validator
    )

    navigation_service = NavigationService(
        timeframe_repo=timeframe_data_repository,
        debug_controller=debug_controller,
        unified_time_manager=unified_time_manager,
        unified_state=unified_state,
        validator=data_validator,
        global_skip_events=global_skip_events,
        universal_renderer=universal_renderer
    )

    debug_service = DebugService(
        debug_controller=debug_controller,
        navigation_service=navigation_service
    )

    position_service = PositionService(
        unified_state=unified_state,
        price_repo=price_repository
    )

    account_service = AccountService()

    logger.info("[INIT] ✅ All components initialized successfully")


# ===== WebSocket Endpoint =====
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket Endpoint mit Command Handling
    REFACTOR PHASE 5: Vollständiger WebSocket-Handler mit Services
    """
    await handle_websocket_commands(
        websocket=websocket,
        manager=manager,
        chart_service=chart_service,
        timeframe_service=timeframe_service,
        navigation_service=navigation_service,
        debug_service=debug_service,
        position_service=position_service,
        account_service=account_service,
        unified_time_manager=unified_time_manager,
        chart_lifecycle_manager=chart_lifecycle_manager,
        data_validator=data_validator,
        DataIntegrityGuard=DataIntegrityGuard,
        global_skip_events=global_skip_events,
        universal_renderer=universal_renderer,
        debug_control_timeframe=debug_control_timeframe
    )


# ===== Startup & Shutdown Events =====
@app.on_event("startup")
async def startup_event():
    """Initialisiert Services beim Server-Start"""
    logger.info("=" * 60)
    logger.info("🚀 RL Trading Chart Server 2.0 startet...")
    logger.info("=" * 60)

    # Initialize all components
    initialize_components()

    # Register routers
    logger.info("[INIT] Registering routes...")

    debug_routes.setup_debug_routes(
        app=app,
        debug_service=debug_service,
        navigation_service=navigation_service,
        unified_time_manager=unified_time_manager,
        manager=manager,
        debug_controller=debug_controller,
        global_skip_events=global_skip_events,
        debug_control_timeframe=debug_control_timeframe,
        account_service=account_service
    )

    account_routes.setup_account_routes(
        app=app,
        account_service=account_service
    )

    chart_routes.setup_chart_routes(
        app=app,
        timeframe_service=timeframe_service,
        manager=manager,
        chart_lifecycle_manager=chart_lifecycle_manager,
        unified_time_manager=unified_time_manager,
        data_validator=data_validator,
        timeframe_data_repository=timeframe_data_repository,
        DataIntegrityGuard=DataIntegrityGuard,
        global_skip_events=global_skip_events,
        universal_renderer=universal_renderer
    )

    static_routes.setup_static_routes(app=app)

    logger.info("✅ Server bereit auf http://localhost:8003")
    logger.info("📖 API Docs: http://localhost:8003/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup beim Server-Shutdown"""
    logger.info("🛑 Server wird heruntergefahren...")
    logger.info("✅ Cleanup abgeschlossen")


# ===== Main Entry Point =====
if __name__ == "__main__":
    print("Starting RL Trading Chart Server 2.0...")
    print("REFACTOR PHASE 5: Complete Modular Server")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        log_level="info"
    )
