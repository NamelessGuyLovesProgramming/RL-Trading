"""
Position Service - Business Logic für Trading Positions
Koordiniert Position-Erstellung, Updates, Schließen
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class PositionService:
    """
    Service für Trading Position Operationen
    Verwaltet Long/Short Positions mit Entry, SL, TP
    """

    def __init__(self,
                 unified_state,  # UnifiedStateManager
                 price_repo):  # UnifiedPriceRepository
        """
        Initialisiert PositionService mit Dependencies

        Args:
            unified_state: Globaler State Manager
            price_repo: Preis-Repository für aktuelle Preise
        """
        self.unified_state = unified_state
        self.price_repo = price_repo

        print("[PositionService] Initialized with dependency injection")

    def create_position(self, entry_price: float, sl_price: float, tp_price: float,
                       direction: str, size: float = 1.0, symbol: str = "NQ") -> Dict[str, Any]:
        """
        Erstellt neue Trading Position

        Args:
            entry_price: Entry-Preis
            sl_price: Stop-Loss Preis
            tp_price: Take-Profit Preis
            direction: 'long' oder 'short'
            size: Positions-Größe
            symbol: Trading-Symbol

        Returns:
            Dict mit position_id, success, position_data
        """
        print(f"[PositionService] Creating {direction} position: Entry={entry_price}, SL={sl_price}, TP={tp_price}")

        # Validiere Direction
        if direction not in ['long', 'short']:
            return {
                'success': False,
                'error': f"Invalid direction: {direction}. Must be 'long' or 'short'"
            }

        # Validiere Preise
        if direction == 'long':
            if sl_price >= entry_price or tp_price <= entry_price:
                return {
                    'success': False,
                    'error': "Long position: SL must be < Entry < TP"
                }
        else:  # short
            if sl_price <= entry_price or tp_price >= entry_price:
                return {
                    'success': False,
                    'error': "Short position: TP < Entry < SL"
                }

        # Erstelle Position
        position_data = {
            'entry_price': entry_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'direction': direction,
            'size': size,
            'symbol': symbol,
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'pnl': 0.0
        }

        # Speichere in State (wenn State-Manager verfügbar)
        if self.unified_state:
            # TODO: Implementiere Position-Storage in UnifiedStateManager
            position_id = f"pos_{datetime.now().timestamp()}"
            print(f"[PositionService] Position created: {position_id}")
        else:
            position_id = "mock_position_id"

        return {
            'success': True,
            'position_id': position_id,
            'position_data': position_data
        }

    def update_position(self, position_id: str, **kwargs) -> Dict[str, Any]:
        """
        Aktualisiert bestehende Position

        Args:
            position_id: Position ID
            **kwargs: Zu aktualisierende Felder (sl_price, tp_price, size)

        Returns:
            Dict mit success, updated_fields
        """
        print(f"[PositionService] Updating position {position_id}: {kwargs}")

        # TODO: Hole Position aus State
        # TODO: Update Position
        # TODO: Speichere zurück in State

        return {
            'success': True,
            'position_id': position_id,
            'updated_fields': list(kwargs.keys())
        }

    def close_position(self, position_id: str, close_price: float) -> Dict[str, Any]:
        """
        Schließt Position

        Args:
            position_id: Position ID
            close_price: Schließ-Preis

        Returns:
            Dict mit success, pnl, close_reason
        """
        print(f"[PositionService] Closing position {position_id} at {close_price}")

        # TODO: Hole Position aus State
        # TODO: Berechne PnL
        # TODO: Update Status auf 'closed'
        # TODO: Speichere zurück in State

        return {
            'success': True,
            'position_id': position_id,
            'close_price': close_price,
            'pnl': 0.0,  # TODO: Echtes PnL berechnen
            'close_reason': 'manual'
        }

    def get_active_positions(self) -> List[Dict[str, Any]]:
        """
        Gibt alle aktiven Positionen zurück

        Returns:
            Liste von Position-Dicts
        """
        print("[PositionService] Getting active positions")

        # TODO: Hole Positionen aus State

        return []

    def calculate_pnl(self, position_id: str, current_price: float) -> Dict[str, Any]:
        """
        Berechnet aktuelles PnL für Position

        Args:
            position_id: Position ID
            current_price: Aktueller Marktpreis

        Returns:
            Dict mit pnl, pnl_percent, unrealized
        """
        print(f"[PositionService] Calculating PnL for {position_id} at {current_price}")

        # TODO: Hole Position
        # TODO: Berechne PnL basierend auf Direction

        return {
            'position_id': position_id,
            'pnl': 0.0,
            'pnl_percent': 0.0,
            'unrealized': True
        }

    def check_stop_loss_hit(self, position_id: str, current_price: float) -> bool:
        """
        Prüft ob Stop-Loss getroffen wurde

        Args:
            position_id: Position ID
            current_price: Aktueller Preis

        Returns:
            True wenn SL getroffen
        """
        # TODO: Hole Position
        # TODO: Prüfe SL basierend auf Direction

        return False

    def check_take_profit_hit(self, position_id: str, current_price: float) -> bool:
        """
        Prüft ob Take-Profit getroffen wurde

        Args:
            position_id: Position ID
            current_price: Aktueller Preis

        Returns:
            True wenn TP getroffen
        """
        # TODO: Hole Position
        # TODO: Prüfe TP basierend auf Direction

        return False
