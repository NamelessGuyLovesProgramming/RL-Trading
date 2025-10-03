"""
Unified State Manager für Chart Server
Single Source of Truth für alle Timeframes
Löst CSV vs DebugController Konflikt
"""

from typing import Optional
from datetime import datetime


class UnifiedStateManager:
    """Zentraler State Manager für timeframe-übergreifende Konsistenz"""

    def __init__(self):
        # CONFLICT RESOLUTION: Unterscheide zwischen Go-To-Date und aktueller Position
        self.initial_go_to_date: Optional[datetime] = None    # Ursprüngliches Go-To-Date vom User
        self.current_skip_position: Optional[datetime] = None # Aktuelle Position nach Skip-Operationen
        self.timeframe_states: dict = {}        # Per-TF States falls nötig
        self.debug_controller_time: Optional[datetime] = None # DebugController Master-Zeit
        self.go_to_date_mode: bool = False     # Ob initial Go-To-Date noch aktiv ist

    def set_go_to_date(self, target_date: datetime) -> None:
        """Setzt Go-To-Date für ALLE Timeframes einheitlich (Initial)"""
        self.initial_go_to_date = target_date
        self.current_skip_position = None  # Reset skip position
        self.debug_controller_time = target_date
        self.go_to_date_mode = True
        print(f"[UNIFIED-STATE] Initial Go-To-Date gesetzt: {target_date} (alle Timeframes)")

    def update_skip_position(self, new_position: datetime, source: str = "skip") -> None:
        """Updates current position after Skip operations - CRITICAL for CSV conflict resolution"""
        old_position = self.current_skip_position
        self.current_skip_position = new_position
        self.debug_controller_time = new_position

        # Nach Skip-Operationen: Go-To-Date Mode deaktivieren für CSV-Loading
        if source == "skip" and self.go_to_date_mode:
            self.go_to_date_mode = False
            print(f"[UNIFIED-STATE] Skip-Position update: {old_position} -> {new_position} (Go-To-Date Mode deaktiviert)")
        else:
            print(f"[UNIFIED-STATE] Position update ({source}): {old_position} -> {new_position}")

    def get_csv_loading_date(self) -> Optional[datetime]:
        """CRITICAL: Gibt korrekte Datum für CSV-Loading zurück (löst CSV vs DebugController Konflikt)"""
        if self.go_to_date_mode and self.initial_go_to_date:
            # Initial Go-To-Date aktiv: Nutze Original-Datum
            print(f"[UNIFIED-STATE] CSV loading: Initial Go-To-Date Mode -> {self.initial_go_to_date.date()}")
            return self.initial_go_to_date
        elif self.current_skip_position:
            # Skip-Position verfügbar: Nutze aktuelle Position
            print(f"[UNIFIED-STATE] CSV loading: Skip Position Mode -> {self.current_skip_position.date()}")
            return self.current_skip_position
        else:
            # Fallback: Standard-Verhalten (neueste Daten)
            print(f"[UNIFIED-STATE] CSV loading: Standard Mode (neueste Daten)")
            return None

    def get_go_to_date(self) -> Optional[datetime]:
        """Legacy compatibility: Gibt Go-To-Date zurück"""
        return self.initial_go_to_date

    def clear_go_to_date(self, reason: str = "unknown") -> None:
        """Cleared Go-To-Date State (mit Logging)"""
        if self.initial_go_to_date is not None or self.current_skip_position is not None:
            print(f"[UNIFIED-STATE] State cleared: Go-To-Date={self.initial_go_to_date}, Skip={self.current_skip_position} (Grund: {reason})")
            self.initial_go_to_date = None
            self.current_skip_position = None
            self.go_to_date_mode = False

    def is_go_to_date_active(self) -> bool:
        """LEGACY: Prüft ob Go-To-Date oder Skip-Position aktiv ist"""
        return self.go_to_date_mode or self.current_skip_position is not None

    def is_csv_date_loading_needed(self) -> bool:
        """NEW: Prüft ob CSV-Loading von spezifischem Datum benötigt wird"""
        return self.go_to_date_mode or self.current_skip_position is not None

    def sync_debug_controller_time(self, new_time: datetime) -> None:
        """Synchronisiert DebugController Zeit global"""
        self.debug_controller_time = new_time
        if not self.go_to_date_mode and not self.current_skip_position:
            print(f"[UNIFIED-STATE] DebugController Zeit global synchronisiert: {new_time}")
