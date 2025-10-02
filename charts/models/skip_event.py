"""
Skip Event Models
Skip-Events für Chart-Navigation
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .chart_data import Candle


@dataclass
class SkipEvent:
    """
    Skip-Event für Chart-Navigation

    Skip-Events werden beim "Skip Forward" erstellt und speichern
    die übersprungenen Kerzen für spätere Darstellung.

    Attributes:
        time: Zeitpunkt des Skip-Events
        candle: Die übersprungene Kerze
        original_timeframe: Ursprungs-Timeframe (z.B. "5m")
        metadata: Zusätzliche Metadaten (optional)
    """
    time: datetime
    candle: Candle
    original_timeframe: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert SkipEvent zu Dictionary für JSON-Serialisierung"""
        return {
            'time': self.time.isoformat() if isinstance(self.time, datetime) else self.time,
            'candle': self.candle.to_dict() if hasattr(self.candle, 'to_dict') else self.candle,
            'original_timeframe': self.original_timeframe,
            'metadata': self.metadata
        }

    @property
    def timestamp(self) -> int:
        """Unix Timestamp des Events"""
        return int(self.time.timestamp())


class SkipEventStore:
    """
    Store für Skip-Events - Single Source of Truth

    Verwaltet alle Skip-Events im System und bietet Methoden
    für das Hinzufügen, Filtern und Löschen von Events.
    """

    def __init__(self):
        """Initialisiert leeren Skip-Event Store"""
        self._events: List[SkipEvent] = []

    def add_event(self, event: SkipEvent) -> None:
        """
        Fügt Skip-Event hinzu

        Args:
            event: SkipEvent-Objekt
        """
        self._events.append(event)

    def add_events(self, events: List[SkipEvent]) -> None:
        """
        Fügt mehrere Skip-Events hinzu

        Args:
            events: Liste von SkipEvent-Objekten
        """
        self._events.extend(events)

    def get_all_events(self) -> List[SkipEvent]:
        """
        Holt alle Skip-Events

        Returns:
            Liste aller gespeicherten SkipEvents
        """
        return self._events.copy()

    def get_events_for_timeframe(self, timeframe: str) -> List[SkipEvent]:
        """
        Holt Skip-Events für spezifischen Timeframe

        Args:
            timeframe: Timeframe-String (z.B. "5m")

        Returns:
            Liste von SkipEvents für den Timeframe
        """
        return [event for event in self._events if event.original_timeframe == timeframe]

    def get_events_in_range(self, start_time: datetime, end_time: datetime) -> List[SkipEvent]:
        """
        Holt Skip-Events in Zeitraum

        Args:
            start_time: Start-Zeitpunkt
            end_time: End-Zeitpunkt

        Returns:
            Liste von SkipEvents im Zeitraum
        """
        return [
            event for event in self._events
            if start_time <= event.time <= end_time
        ]

    def clear(self) -> None:
        """Löscht alle Skip-Events"""
        self._events.clear()

    def clear_timeframe(self, timeframe: str) -> None:
        """
        Löscht Skip-Events für spezifischen Timeframe

        Args:
            timeframe: Timeframe-String (z.B. "5m")
        """
        self._events = [
            event for event in self._events
            if event.original_timeframe != timeframe
        ]

    def count(self) -> int:
        """
        Anzahl der gespeicherten Skip-Events

        Returns:
            Anzahl Events
        """
        return len(self._events)

    def count_by_timeframe(self, timeframe: str) -> int:
        """
        Anzahl Skip-Events für Timeframe

        Args:
            timeframe: Timeframe-String

        Returns:
            Anzahl Events für diesen Timeframe
        """
        return len(self.get_events_for_timeframe(timeframe))

    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertiert Store zu Dictionary

        Returns:
            Dictionary mit allen Events
        """
        return {
            'events': [event.to_dict() for event in self._events],
            'total_count': len(self._events)
        }

    def __len__(self) -> int:
        """Anzahl Events (für len(store))"""
        return len(self._events)

    def __repr__(self) -> str:
        """String-Repräsentation"""
        return f"SkipEventStore(events={len(self._events)})"
