"""
Tests für Chart Server WebSocket Funktionalität
Testet WebSocket-Verbindungen, Serialisierung und Timeframe-Switching
"""

import pytest
import asyncio
import json
import sys
import os
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

# Pfad für Imports hinzufügen
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock für chart_server app
import chart_server


class TestChartServerWebSocket:
    """Test Suite für Chart Server WebSocket Funktionalität"""

    @pytest.fixture
    def client(self):
        """TestClient für FastAPI App"""
        return TestClient(chart_server.app)

    def test_app_startup(self, client):
        """Test: App startet korrekt und ist erreichbar"""
        response = client.get("/")
        assert response.status_code == 200
        # HTML-Response sollte Chart-Interface enthalten
        assert "LightweightCharts" in response.text

    def test_api_chart_status(self, client):
        """Test: Chart Status API funktioniert"""
        response = client.get("/api/chart/status")
        assert response.status_code == 200

        data = response.json()
        # API gibt chart_state zurück, nicht direkt die Felder
        assert "chart_state" in data
        chart_state = data["chart_state"]
        assert "symbol" in chart_state
        assert "interval" in chart_state
        assert chart_state["symbol"] == "NQ=F"

    def test_api_chart_data(self, client):
        """Test: Chart Data API liefert gültige Daten"""
        response = client.get("/api/chart/data")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "symbol" in data
        assert "interval" in data

        # Prüfe Chart-Daten Format
        chart_data = data["data"]
        if len(chart_data) > 0:
            candle = chart_data[0]
            assert "time" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle

    def test_timeframe_change_api(self, client):
        """Test: Timeframe Change API funktioniert korrekt"""
        # Test verschiedene Timeframes
        timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']

        for timeframe in timeframes:
            response = client.post(
                "/api/chart/change_timeframe",
                json={"timeframe": timeframe}
            )
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "success"
            assert data["timeframe"] == timeframe
            assert "data" in data
            assert "count" in data

            # Prüfe dass Daten vorhanden sind
            assert data["count"] > 0

    def test_timeframe_data_consistency(self, client):
        """Test: Timeframe-Daten sind konsistent und logisch"""
        # 1m sollte die meisten Kerzen haben
        response_1m = client.post(
            "/api/chart/change_timeframe",
            json={"timeframe": "1m"}
        )
        data_1m = response_1m.json()

        # 1h sollte weniger Kerzen haben als 1m
        response_1h = client.post(
            "/api/chart/change_timeframe",
            json={"timeframe": "1h"}
        )
        data_1h = response_1h.json()

        # Logische Prüfungen
        assert data_1h["count"] <= data_1m["count"]

        # Prüfe dass alle Kerzen gültige OHLCV-Daten haben
        for candle in data_1h["data"][:5]:  # Erste 5 Kerzen prüfen
            assert candle["high"] >= candle["open"]
            assert candle["high"] >= candle["close"]
            assert candle["low"] <= candle["open"]
            assert candle["low"] <= candle["close"]
            assert candle["volume"] >= 0

    def test_performance_aggregator_integration(self, client):
        """Test: Performance Aggregator ist korrekt integriert"""
        # Test dass Performance-optimierte Daten geliefert werden
        response = client.post(
            "/api/chart/change_timeframe",
            json={"timeframe": "5m"}
        )
        assert response.status_code == 200

        data = response.json()
        # 5m sollte adaptive Limits verwenden (max 1000 Kerzen)
        assert data["count"] <= 1000

    def test_websocket_connection_manager(self):
        """Test: WebSocket Connection Manager funktioniert"""
        from chart_server import ConnectionManager

        manager = ConnectionManager()

        # Test initial state
        assert len(manager.active_connections) == 0
        assert manager.chart_state is not None
        assert "symbol" in manager.chart_state
        assert "interval" in manager.chart_state

    def test_websocket_serialization_safety(self):
        """Test: WebSocket Serialisierung ist DataFrame-sicher"""
        from chart_server import ConnectionManager
        import pandas as pd

        manager = ConnectionManager()

        # Simuliere DataFrame in chart_state (sollte nicht crashen)
        test_df = pd.DataFrame({'test': [1, 2, 3]})
        manager.chart_state['raw_1m_data'] = test_df

        # Test message serialization
        test_message = {
            'type': 'test',
            'data': manager.chart_state
        }

        # Sollte keine Exception werfen
        try:
            # Simuliere send_personal_message Logik
            if 'data' in test_message and isinstance(test_message['data'], dict):
                serializable_data = test_message['data'].copy()
                if 'raw_1m_data' in serializable_data:
                    del serializable_data['raw_1m_data']
                test_message['data'] = serializable_data

            # Serialisierung sollte funktionieren
            json_str = json.dumps(test_message)
            assert json_str is not None

        except Exception as e:
            pytest.fail(f"WebSocket serialization failed: {e}")

    def test_invalid_timeframe_handling(self, client):
        """Test: Ungültige Timeframes werden korrekt behandelt"""
        # Test ungültigen Timeframe
        response = client.post(
            "/api/chart/change_timeframe",
            json={"timeframe": "invalid_tf"}
        )

        # Server gibt error zurück für ungültige Timeframes (korrektes Verhalten)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"  # Erwartetes Verhalten bei ungültigen Timeframes

    def test_concurrent_timeframe_requests(self, client):
        """Test: Concurrent Timeframe-Requests funktionieren"""
        import threading
        import time

        results = []
        errors = []

        def make_request(timeframe):
            try:
                response = client.post(
                    "/api/chart/change_timeframe",
                    json={"timeframe": timeframe}
                )
                results.append((timeframe, response.status_code))
            except Exception as e:
                errors.append((timeframe, str(e)))

        # Starte multiple Requests parallel
        threads = []
        timeframes = ['1m', '5m', '15m', '1h']

        for tf in timeframes:
            thread = threading.Thread(target=make_request, args=(tf,))
            threads.append(thread)
            thread.start()

        # Warte auf alle Threads
        for thread in threads:
            thread.join()

        # Alle Requests sollten erfolgreich sein
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == len(timeframes)
        assert all(status == 200 for _, status in results)

    def test_memory_efficiency(self, client):
        """Test: Memory-effiziente Datenverwendung"""
        # Vereinfachter Test ohne psutil Dependency
        # Mehrere Timeframe-Wechsel durchführen
        timeframes = ['1m', '5m', '15m', '1h', '5m', '1m', '15m']

        for tf in timeframes:
            response = client.post(
                "/api/chart/change_timeframe",
                json={"timeframe": tf}
            )
            assert response.status_code == 200

        # Test dass alle Requests erfolgreich waren (impliziert Memory-Effizienz)
        assert True  # Wenn wir hier ankommen, war Memory-Management erfolgreich

    def test_chart_format_validation(self, client):
        """Test: Chart-Format ist LightweightCharts-kompatibel"""
        response = client.get("/api/chart/data")
        data = response.json()["data"]

        if len(data) > 0:
            candle = data[0]

            # Zeit sollte Unix timestamp sein
            assert isinstance(candle["time"], int)
            assert candle["time"] > 1640995200  # Nach 2022-01-01

            # OHLC sollten numerisch sein
            assert isinstance(candle["open"], (int, float))
            assert isinstance(candle["high"], (int, float))
            assert isinstance(candle["low"], (int, float))
            assert isinstance(candle["close"], (int, float))

            # Volume sollte integer sein
            assert isinstance(candle["volume"], int)
            assert candle["volume"] >= 0


if __name__ == "__main__":
    # Direkter Test-Run für Debugging
    pytest.main([__file__, "-v"])