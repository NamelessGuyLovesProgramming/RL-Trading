"""
Debug Service - Business Logic für Debug-Mode
Koordiniert Debug-Funktionalität, Auto-Play, Speed-Control
"""

from typing import Dict, Any, Optional


class DebugService:
    """
    Service für Debug-Mode Operationen
    Verwaltet Debug-Aktivierung, Auto-Play, Speed-Control
    """

    def __init__(self,
                 debug_controller,  # DebugController
                 navigation_service):  # NavigationService
        """
        Initialisiert DebugService mit Dependencies

        Args:
            debug_controller: Debug Controller
            navigation_service: Navigation Service für Skip-Operationen
        """
        self.controller = debug_controller
        self.nav_service = navigation_service

        print("[DebugService] Initialized with dependency injection")

    def activate_debug_mode(self, start_date=None) -> Dict[str, Any]:
        """
        Aktiviert Debug-Modus

        Args:
            start_date: Optional Start-Datum

        Returns:
            Dict mit success, current_time, timeframe
        """
        print(f"[DebugService] Activating debug mode: {start_date}")

        if start_date:
            self.controller.set_start_time(start_date)

        current_time = self.controller.current_time
        timeframe = self.controller.current_timeframe

        print(f"[DebugService] Debug mode active: {current_time} ({timeframe})")

        return {
            'success': True,
            'current_time': current_time,
            'timeframe': timeframe
        }

    def toggle_play_mode(self) -> Dict[str, Any]:
        """
        Toggle Play/Pause Modus

        Returns:
            Dict mit play_mode (bool), speed
        """
        play_mode = self.controller.toggle_play_mode()

        print(f"[DebugService] Play mode: {'ON' if play_mode else 'OFF'}")

        return {
            'play_mode': play_mode,
            'speed': self.controller.speed
        }

    def set_speed(self, speed: float) -> Dict[str, Any]:
        """
        Setzt Auto-Play Geschwindigkeit

        Args:
            speed: Geschwindigkeit (1-15)

        Returns:
            Dict mit success, speed
        """
        print(f"[DebugService] Setting speed: {speed}x")

        self.controller.set_speed(speed)

        return {
            'success': True,
            'speed': self.controller.speed
        }

    def get_debug_state(self) -> Dict[str, Any]:
        """
        Gibt aktuellen Debug-Status zurück

        Returns:
            Dict mit current_time, timeframe, play_mode, speed, incomplete_candles
        """
        state = self.controller.get_state()

        return {
            'current_time': state['current_time'],
            'timeframe': state['timeframe'],
            'play_mode': state['play_mode'],
            'speed': state['speed'],
            'incomplete_candles': state['incomplete_candles'],
            'aggregator_state': state.get('aggregator_state', {})
        }

    def set_timeframe(self, timeframe: str) -> Dict[str, Any]:
        """
        Ändert Debug-Timeframe

        Args:
            timeframe: Ziel-Timeframe

        Returns:
            Dict mit success, timeframe
        """
        print(f"[DebugService] Setting debug timeframe: {timeframe}")

        self.controller.set_timeframe(timeframe)

        return {
            'success': True,
            'timeframe': timeframe
        }

    def skip_minute(self) -> Dict[str, Any]:
        """
        Skip +1 Minute (für manuelle Debug-Navigation)

        Returns:
            Dict mit candle, candle_type
        """
        print("[DebugService] Skip +1 minute")

        result = self.controller.skip_minute()

        return {
            'candle': result.get('candle') if result else None,
            'candle_type': result.get('type') if result else None,
            'timeframe': result.get('timeframe') if result else None
        }

    def auto_play_tick(self, timeframe: str) -> Dict[str, Any]:
        """
        Auto-Play Tick (wird vom Background-Task aufgerufen)

        Args:
            timeframe: Aktueller Timeframe

        Returns:
            Dict mit candle, success
        """
        if not self.controller.play_mode:
            return {'success': False, 'reason': 'play_mode_off'}

        # Nutze NavigationService für Skip
        skip_result = self.nav_service.skip_forward(timeframe)

        return skip_result
