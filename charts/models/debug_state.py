"""
Debug State Models
Debug-Modus Zustandsverwaltung
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class DebugState:
    """
    Debug-Modus Zustand

    Verwaltet den Zustand des Debug-Modus für Chart-Debugging
    und Testing-Szenarien.

    Attributes:
        active: Ob Debug-Modus aktiv ist
        current_date: Aktuelles Debug-Datum (für zeitbasiertes Debugging)
        speed: Playback-Geschwindigkeit (1.0 = normal, 2.0 = doppelt, 0.5 = halb)
        auto_play: Ob Auto-Play aktiv ist
        start_date: Start-Datum des Debug-Modus
        paused: Ob Debug-Modus pausiert ist
        step_count: Anzahl der Schritte im Debug-Modus
        metadata: Zusätzliche Metadaten
    """
    active: bool = False
    current_date: Optional[datetime] = None
    speed: float = 1.0
    auto_play: bool = False
    start_date: Optional[datetime] = None
    paused: bool = False
    step_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert DebugState zu Dictionary für JSON-Serialisierung"""
        return {
            'active': self.active,
            'current_date': self.current_date.isoformat() if self.current_date else None,
            'speed': self.speed,
            'auto_play': self.auto_play,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'paused': self.paused,
            'step_count': self.step_count,
            'metadata': self.metadata
        }

    def activate(self, start_date: datetime) -> None:
        """
        Aktiviert Debug-Modus

        Args:
            start_date: Start-Datum für Debug-Modus
        """
        self.active = True
        self.start_date = start_date
        self.current_date = start_date
        self.step_count = 0
        self.paused = False

    def deactivate(self) -> None:
        """Deaktiviert Debug-Modus"""
        self.active = False
        self.auto_play = False
        self.paused = False
        self.current_date = None

    def play(self) -> None:
        """Startet Auto-Play"""
        if not self.active:
            return
        self.auto_play = True
        self.paused = False

    def pause(self) -> None:
        """Pausiert Auto-Play"""
        self.auto_play = False
        self.paused = True

    def stop(self) -> None:
        """Stoppt Auto-Play"""
        self.auto_play = False
        self.paused = False

    def step_forward(self, date: Optional[datetime] = None) -> None:
        """
        Schritt vorwärts im Debug-Modus

        Args:
            date: Neues Datum (optional, sonst wird auto-incrementiert)
        """
        if not self.active:
            return

        if date:
            self.current_date = date

        self.step_count += 1

    def set_speed(self, speed: float) -> None:
        """
        Setzt Playback-Geschwindigkeit

        Args:
            speed: Geschwindigkeitsfaktor (0.5 - 10.0)
        """
        # Validierung: Geschwindigkeit zwischen 0.5x und 10x
        self.speed = max(0.5, min(10.0, speed))

    def reset(self) -> None:
        """Setzt Debug-State zurück"""
        if self.start_date:
            self.current_date = self.start_date
        self.step_count = 0
        self.paused = False
        self.auto_play = False

    @property
    def is_running(self) -> bool:
        """Prüft ob Debug-Modus läuft (aktiv und nicht pausiert)"""
        return self.active and not self.paused

    @property
    def is_paused(self) -> bool:
        """Prüft ob Debug-Modus pausiert ist"""
        return self.active and self.paused

    @property
    def delay_ms(self) -> int:
        """
        Berechnet Delay in Millisekunden basierend auf Speed

        Returns:
            Delay in Millisekunden für Auto-Play
        """
        # Basis-Delay: 1000ms bei Speed 1.0
        base_delay = 1000
        return int(base_delay / self.speed)

    def __repr__(self) -> str:
        """String-Repräsentation"""
        status = "active" if self.active else "inactive"
        if self.active:
            if self.auto_play:
                status += " (playing)"
            elif self.paused:
                status += " (paused)"
        return f"DebugState({status}, speed={self.speed}x, steps={self.step_count})"
