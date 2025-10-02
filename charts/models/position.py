"""
Position Models
Trading-Positionen und Position-Boxen
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class PositionDirection(str, Enum):
    """Position-Richtung"""
    LONG = "long"
    SHORT = "short"


class PositionStatus(str, Enum):
    """Position-Status"""
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class Position:
    """
    Trading-Position

    Attributes:
        id: Eindeutige Position-ID
        entry_price: Einstiegspreis
        sl_price: Stop-Loss Preis
        tp_price: Take-Profit Preis
        entry_time: Einstiegszeitpunkt
        direction: Position-Richtung (long/short)
        status: Position-Status (open/closed/cancelled)
        exit_price: Ausstiegspreis (optional)
        exit_time: Ausstiegszeitpunkt (optional)
        pnl: Profit/Loss (optional)
        metadata: Zusätzliche Metadaten
    """
    id: str
    entry_price: float
    sl_price: float
    tp_price: float
    entry_time: datetime
    direction: PositionDirection
    status: PositionStatus = PositionStatus.OPEN
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert Position zu Dictionary für JSON-Serialisierung"""
        return {
            'id': self.id,
            'entry_price': self.entry_price,
            'sl_price': self.sl_price,
            'tp_price': self.tp_price,
            'entry_time': self.entry_time.isoformat() if isinstance(self.entry_time, datetime) else self.entry_time,
            'direction': self.direction.value if isinstance(self.direction, PositionDirection) else self.direction,
            'status': self.status.value if isinstance(self.status, PositionStatus) else self.status,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if isinstance(self.exit_time, datetime) and self.exit_time else self.exit_time,
            'pnl': self.pnl,
            'metadata': self.metadata
        }

    @property
    def is_open(self) -> bool:
        """Prüft ob Position offen ist"""
        return self.status == PositionStatus.OPEN

    @property
    def is_closed(self) -> bool:
        """Prüft ob Position geschlossen ist"""
        return self.status == PositionStatus.CLOSED

    @property
    def is_long(self) -> bool:
        """Prüft ob Position Long ist"""
        return self.direction == PositionDirection.LONG

    @property
    def is_short(self) -> bool:
        """Prüft ob Position Short ist"""
        return self.direction == PositionDirection.SHORT

    @property
    def risk_range(self) -> float:
        """Berechnet Risiko-Range (Entry bis SL)"""
        return abs(self.entry_price - self.sl_price)

    @property
    def reward_range(self) -> float:
        """Berechnet Reward-Range (Entry bis TP)"""
        return abs(self.tp_price - self.entry_price)

    @property
    def risk_reward_ratio(self) -> float:
        """Berechnet Risk-Reward Ratio"""
        if self.risk_range == 0:
            return 0.0
        return self.reward_range / self.risk_range

    def close(self, exit_price: float, exit_time: datetime) -> None:
        """
        Schließt Position

        Args:
            exit_price: Ausstiegspreis
            exit_time: Ausstiegszeitpunkt
        """
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.status = PositionStatus.CLOSED
        self.pnl = self._calculate_pnl(exit_price)

    def cancel(self) -> None:
        """Storniert Position"""
        self.status = PositionStatus.CANCELLED

    def _calculate_pnl(self, exit_price: float) -> float:
        """
        Berechnet PnL

        Args:
            exit_price: Ausstiegspreis

        Returns:
            Profit/Loss
        """
        if self.direction == PositionDirection.LONG:
            return exit_price - self.entry_price
        else:  # SHORT
            return self.entry_price - exit_price


@dataclass
class PositionBox:
    """
    Position-Box für Chart-Darstellung

    Wrapper um Position mit zusätzlichen Chart-spezifischen Daten
    wie gecachte Pixel-Koordinaten für Performance-Optimierung.

    Attributes:
        position: Die eigentliche Trading-Position
        cached_pixel_coordinates: Gecachte Pixel-Koordinaten für Chart-Rendering
        visible: Sichtbarkeit im Chart
        metadata: Zusätzliche Chart-Metadaten
    """
    position: Position
    cached_pixel_coordinates: Optional[Dict[str, Any]] = None
    visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert PositionBox zu Dictionary"""
        return {
            'position': self.position.to_dict(),
            'cached_pixel_coordinates': self.cached_pixel_coordinates,
            'visible': self.visible,
            'metadata': self.metadata
        }

    @property
    def position_id(self) -> str:
        """Position-ID (Shortcut)"""
        return self.position.id

    def update_pixel_coordinates(self, coordinates: Dict[str, Any]) -> None:
        """
        Aktualisiert gecachte Pixel-Koordinaten

        Args:
            coordinates: Dictionary mit Pixel-Koordinaten
        """
        self.cached_pixel_coordinates = coordinates
        # Timestamp hinzufügen für Cache-Invalidierung
        self.cached_pixel_coordinates['timestamp'] = datetime.now().isoformat()

    def clear_cache(self) -> None:
        """Löscht gecachte Koordinaten"""
        self.cached_pixel_coordinates = None

    def has_cached_coordinates(self) -> bool:
        """Prüft ob Koordinaten gecacht sind"""
        return self.cached_pixel_coordinates is not None

    def show(self) -> None:
        """Macht Position-Box sichtbar"""
        self.visible = True

    def hide(self) -> None:
        """Versteckt Position-Box"""
        self.visible = False

    def __repr__(self) -> str:
        """String-Repräsentation"""
        return f"PositionBox(id={self.position.id}, visible={self.visible}, cached={self.has_cached_coordinates()})"
