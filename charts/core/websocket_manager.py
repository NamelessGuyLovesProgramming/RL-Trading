"""
WebSocket Connection Manager
Verwaltet WebSocket-Verbindungen für Realtime Chart-Updates
"""

from typing import List, Dict, Any, Optional
from fastapi import WebSocket
import json
import asyncio
import logging
from datetime import datetime


# JSON Serializer Helper (wird hier lokal definiert)
def json_serializer(obj):
    """Custom JSON serializer für datetime und andere nicht-serialisierbare Objekte"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):
        try:
            result = {}
            for key, value in obj.__dict__.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif not callable(value):
                    result[key] = value
            return result
        except:
            return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class ConnectionManager:
    """Verwaltet WebSocket-Verbindungen für Realtime-Updates"""

    def __init__(self, initial_chart_data: List[Dict[str, Any]] = None, data_guard=None):
        """
        Args:
            initial_chart_data: Initiale Chart-Daten beim Server-Start
            data_guard: DataIntegrityGuard für Validierung (optional)
        """
        self.active_connections: List[WebSocket] = []
        self.data_guard = data_guard
        self.chart_state: Dict[str, Any] = {
            'data': initial_chart_data or [],
            'symbol': 'NQ=F',
            'interval': '5m',  # 5-Minuten Standard
            'last_update': datetime.now().isoformat(),
            'positions': [],
            'raw_1m_data': None  # CSV-basiert, kein raw data needed
        }

    async def connect(self, websocket: WebSocket) -> None:
        """Neue WebSocket-Verbindung hinzufügen"""
        await websocket.accept()
        self.active_connections.append(websocket)

        # Sende aktuellen Chart-State an neuen Client
        await self.send_personal_message({
            'type': 'initial_data',
            'data': self.chart_state
        }, websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """WebSocket-Verbindung entfernen"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        """Nachricht an spezifischen Client senden"""
        try:
            # Erstelle eine serialisierbare Kopie der Daten ohne DataFrame
            if 'data' in message and isinstance(message['data'], dict):
                serializable_data = message['data'].copy()
                # Entferne nicht-serialisierbare DataFrame-Objekte
                if 'raw_1m_data' in serializable_data:
                    del serializable_data['raw_1m_data']
                message = message.copy()
                message['data'] = serializable_data

            # Verwende custom serializer für datetime Objekte
            await websocket.send_text(json.dumps(message, default=json_serializer))
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            # Debug: Drucke Details für JSON Serialization Fehler
            if "not JSON serializable" in str(e):
                logging.error(f"Message contents: {message}")

    async def broadcast(self, message: dict) -> None:
        """🛡️ CRASH-SAFE Nachricht an alle verbundenen Clients senden"""
        print(f"Broadcast: {len(self.active_connections)} aktive Verbindungen, Nachricht: {message.get('type', 'unknown')}")

        if not self.active_connections:
            print("WARNUNG: Keine aktiven WebSocket-Verbindungen für Broadcast!")
            return

        # CRITICAL: DataIntegrityGuard Validierung (falls verfügbar)
        if self.data_guard and hasattr(self.data_guard, 'validate_websocket_message'):
            if not self.data_guard.validate_websocket_message(message):
                print(f"[DATA-GUARD] [BLOCKED] BLOCKED invalid websocket message: {message.get('type', 'unknown')}")
                return

        # Sende parallel an alle Clients
        tasks = []
        for connection in self.active_connections.copy():
            tasks.append(self.send_personal_message(message, connection))

        # Warte auf alle Sends (mit Error-Handling)
        await asyncio.gather(*tasks, return_exceptions=True)
        print(f"Broadcast abgeschlossen an {len(self.active_connections)} Clients")

    def update_chart_state(self, update_data: dict) -> None:
        """Chart-State aktualisieren"""
        if update_data.get('type') == 'set_data':
            self.chart_state['data'] = update_data.get('data', [])
            self.chart_state['symbol'] = update_data.get('symbol', 'NQ=F')
            self.chart_state['interval'] = update_data.get('interval', '5m')
        elif update_data.get('type') == 'add_candle':
            # Neue Kerze hinzufügen
            candle = update_data.get('candle')
            if candle:
                self.chart_state['data'].append(candle)
        elif update_data.get('type') == 'add_position':
            # Position Overlay hinzufügen
            if 'positions' not in self.chart_state:
                self.chart_state['positions'] = []
            position = update_data.get('position')
            if position:
                self.chart_state['positions'].append(position)
        elif update_data.get('type') == 'remove_position':
            # Position entfernen
            position_id = update_data.get('position_id')
            if position_id and 'positions' in self.chart_state:
                self.chart_state['positions'] = [
                    p for p in self.chart_state['positions']
                    if p.get('id') != position_id
                ]

        self.chart_state['last_update'] = datetime.now().isoformat()
