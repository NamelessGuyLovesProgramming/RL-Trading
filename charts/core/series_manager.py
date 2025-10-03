"""
Series Manager für Chart-Lifecycle Management
Enthält ChartSeriesLifecycleManager für State Machine & Chart Recreation
"""


class ChartSeriesLifecycleManager:
    """
    🚀 REVOLUTIONARY: Chart Series State Machine & Factory Pattern
    Komplett löst das "Value is null" Problem durch saubere Chart-Recreation

    Problem: Skip-generierte Kerzen korruption Chart Series interne State
    Lösung: Komplette Chart Series Destruction & Recreation bei Timeframe-Wechseln
    """

    def __init__(self):
        # Chart Series States
        self.STATES = {
            'CLEAN': 'clean',           # Sauberer Zustand nach Initialization
            'DATA_LOADED': 'data_loaded', # Data geladen und validiert
            'SKIP_MODIFIED': 'skip_modified', # Skip-Operationen haben State modifiziert
            'CORRUPTED': 'corrupted',   # Chart Series korrupt, braucht Recreation
            'TRANSITIONING': 'transitioning'  # Gerade während Timeframe-Wechsel
        }

        # Current Chart State
        self.current_state = self.STATES['CLEAN']
        self.last_timeframe = None
        self.skip_operations_count = 0
        self.chart_series_version = 1  # Inkrementiert bei jeder Recreation

        print("[CHART-LIFECYCLE] Initialized - State: CLEAN")

    def track_skip_operation(self, timeframe):
        """Trackt Skip-Operationen und markiert Chart als potentiell korrupt"""
        if self.current_state == self.STATES['CLEAN']:
            self.current_state = self.STATES['SKIP_MODIFIED']

        self.skip_operations_count += 1
        self.last_timeframe = timeframe

        print(f"[CHART-LIFECYCLE] Skip operation tracked (#{self.skip_operations_count}) - State: {self.current_state}")

    def prepare_timeframe_transition(self, from_timeframe, to_timeframe):
        """Bereitet sauberen Timeframe-Übergang vor"""

        # CRITICAL FIX: Prüfe State BEVOR er auf TRANSITIONING gesetzt wird
        was_corrupted = self.current_state == self.STATES['CORRUPTED']
        was_skip_modified = self.current_state == self.STATES['SKIP_MODIFIED']
        has_skip_operations = self.skip_operations_count > 0

        print(f"[CHART-LIFECYCLE] Pre-transition state check: corrupted={was_corrupted}, skip_modified={was_skip_modified}, skip_count={has_skip_operations}")

        self.current_state = self.STATES['TRANSITIONING']

        # ENHANCED LOGIC: Chart Recreation bei verschiedenen Corruptions-Szenarien
        needs_recreation = (
            has_skip_operations or          # Skip-Operationen haben State modifiziert
            was_corrupted or               # Chart war bereits als korrupt markiert
            was_skip_modified              # Chart war im SKIP_MODIFIED State
        )

        transition_plan = {
            'needs_recreation': needs_recreation,
            'from_timeframe': from_timeframe,
            'to_timeframe': to_timeframe,
            'skip_count': self.skip_operations_count,
            'reason': 'skip_contamination' if self.skip_operations_count > 0 else 'corruption_detected'
        }

        recreation_reason = []
        if has_skip_operations:
            recreation_reason.append(f"skip_operations({self.skip_operations_count})")
        if was_corrupted:
            recreation_reason.append("was_corrupted")
        if was_skip_modified:
            recreation_reason.append("was_skip_modified")

        reason_text = " + ".join(recreation_reason) if recreation_reason else "no_recreation_needed"

        print(f"[CHART-LIFECYCLE] Transition plan: {from_timeframe} -> {to_timeframe}, Recreation: {needs_recreation} ({reason_text})")
        return transition_plan

    def get_chart_recreation_command(self):
        """Factory Method: Erstellt Command für Chart Recreation"""
        self.chart_series_version += 1

        return {
            'action': 'recreate_chart_series',
            'version': self.chart_series_version,
            'clear_strategy': 'complete_destruction',  # Komplett zerstören, nicht nur clearen
            'validation_level': 'ultra_strict',
            'recovery_fallback': 'emergency_reload'
        }

    def complete_timeframe_transition(self, success=True):
        """Schließt Timeframe-Übergang ab und setzt neuen State"""
        if success:
            self.current_state = self.STATES['DATA_LOADED']
            self.skip_operations_count = 0  # Reset nach erfolgreichem Übergang
            print(f"[CHART-LIFECYCLE] Transition completed successfully - State: DATA_LOADED (v{self.chart_series_version})")
        else:
            self.current_state = self.STATES['CORRUPTED']
            print(f"[CHART-LIFECYCLE] Transition FAILED - State: CORRUPTED")

    def mark_chart_corrupted(self, reason="unknown"):
        """Markiert Chart als korrupt - erzwingt Recreation beim nächsten Übergang"""
        self.current_state = self.STATES['CORRUPTED']
        print(f"[CHART-LIFECYCLE] Chart marked as CORRUPTED: {reason}")

    def reset_to_clean_state(self):
        """Reset zu sauberem Zustand (z.B. nach Go To Date)"""
        print(f"[CHART-LIFECYCLE] Starting CLEAN RESET - Previous state: {self.current_state}, Skip count: {self.skip_operations_count}")

        self.current_state = self.STATES['CLEAN']
        self.skip_operations_count = 0
        self.chart_series_version += 1

        print(f"[CHART-LIFECYCLE] CLEAN RESET COMPLETE - Version: {self.chart_series_version}, State: CLEAN")

        # ENHANCED: Verify clean state
        if self.skip_operations_count == 0 and self.current_state == self.STATES['CLEAN']:
            print(f"[CHART-LIFECYCLE] CLEAN STATE VERIFIED: Ready for timeframe operations")
        else:
            print(f"[CHART-LIFECYCLE] WARNING: Reset verification failed!")

    def force_chart_recreation_on_next_transition(self):
        """EMERGENCY: Forciert Chart Recreation beim nächsten Timeframe-Wechsel"""
        self.current_state = self.STATES['CORRUPTED']
        print(f"[CHART-LIFECYCLE] EMERGENCY: Forced chart recreation on next transition")

    def get_state_info(self):
        """Debug Info über aktuellen Chart State"""
        return {
            'state': self.current_state,
            'skip_count': self.skip_operations_count,
            'version': self.chart_series_version,
            'last_timeframe': self.last_timeframe
        }
