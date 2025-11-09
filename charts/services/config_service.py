"""
Config Service für persistente Speicherung
Verwaltet Account Balances und globale Zeit-Einstellungen
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigService:
    """
    Service für persistente Config-Speicherung

    Speichert:
    - Account Balances (RL-KI + Nutzer)
    - Globale Zeit-Einstellungen (optional)
    """

    def __init__(self, config_dir: str = "charts/config"):
        """Initialisiert ConfigService mit Config-Verzeichnis"""
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "persistent_state.json"

        # Erstelle Config-Directory falls nicht vorhanden
        self._ensure_config_directory()

        # Lade oder erstelle Default-Config
        self.config = self._load_or_create_config()

        logger.info(f"[ConfigService] Initialized with config: {self.config_file}")

    def _ensure_config_directory(self) -> None:
        """Erstellt Config-Verzeichnis falls nicht vorhanden"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[ConfigService] Created config directory: {self.config_dir}")

    def _load_or_create_config(self) -> Dict[str, Any]:
        """Lädt Config oder erstellt Default-Config"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"[ConfigService] Config loaded from {self.config_file}")
                return config
            except Exception as e:
                logger.error(f"[ConfigService] Error loading config: {e}")
                logger.info("[ConfigService] Creating default config")
                return self._create_default_config()
        else:
            logger.info("[ConfigService] No config found, creating default")
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Erstellt Default-Config mit 500k Start-Balance"""
        default_config = {
            "accounts": {
                "ai_balance": 500000,
                "user_balance": 500000
            },
            "time": {
                "current_debug_time": None,
                "initial_go_to_date": None
            },
            "version": "1.0"
        }

        # Speichere Default-Config
        self._save_config(default_config)
        logger.info("[ConfigService] Default config created with 500.000€ per account")

        return default_config

    def _save_config(self, config: Dict[str, Any]) -> None:
        """Speichert Config in JSON-File"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"[ConfigService] Config saved to {self.config_file}")
        except Exception as e:
            logger.error(f"[ConfigService] Error saving config: {e}")

    def get_account_balances(self) -> Dict[str, float]:
        """
        Gibt Account-Balances zurück

        Returns:
            {"ai_balance": 500000.0, "user_balance": 500000.0}
        """
        accounts = self.config.get("accounts", {})
        return {
            "ai_balance": float(accounts.get("ai_balance", 500000)),
            "user_balance": float(accounts.get("user_balance", 500000))
        }

    def update_account_balances(self, ai_balance: float = None, user_balance: float = None) -> bool:
        """
        Aktualisiert Account-Balances und speichert Config

        Args:
            ai_balance: Neue RL-KI Balance (optional)
            user_balance: Neue Nutzer Balance (optional)

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            if "accounts" not in self.config:
                self.config["accounts"] = {}

            if ai_balance is not None:
                self.config["accounts"]["ai_balance"] = float(ai_balance)
                logger.info(f"[ConfigService] AI Balance updated: {ai_balance}€")

            if user_balance is not None:
                self.config["accounts"]["user_balance"] = float(user_balance)
                logger.info(f"[ConfigService] User Balance updated: {user_balance}€")

            self._save_config(self.config)
            return True

        except Exception as e:
            logger.error(f"[ConfigService] Error updating balances: {e}")
            return False

    def get_time_config(self) -> Dict[str, Optional[str]]:
        """
        Gibt Zeit-Config zurück

        Returns:
            {"current_debug_time": "2024-01-15T10:30:00", "initial_go_to_date": None}
        """
        time_config = self.config.get("time", {})
        return {
            "current_debug_time": time_config.get("current_debug_time"),
            "initial_go_to_date": time_config.get("initial_go_to_date")
        }

    def update_time_config(self, current_debug_time: str = None, initial_go_to_date: str = None) -> bool:
        """
        Aktualisiert Zeit-Config (optional für spätere Verwendung)

        Args:
            current_debug_time: ISO-Format Zeitstring
            initial_go_to_date: ISO-Format Zeitstring

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        try:
            if "time" not in self.config:
                self.config["time"] = {}

            if current_debug_time is not None:
                self.config["time"]["current_debug_time"] = current_debug_time
                logger.info(f"[ConfigService] Debug time updated: {current_debug_time}")

            if initial_go_to_date is not None:
                self.config["time"]["initial_go_to_date"] = initial_go_to_date
                logger.info(f"[ConfigService] Go-To-Date updated: {initial_go_to_date}")

            self._save_config(self.config)
            return True

        except Exception as e:
            logger.error(f"[ConfigService] Error updating time config: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """
        Setzt Config auf Default-Werte zurück

        Returns:
            True wenn erfolgreich
        """
        try:
            self.config = self._create_default_config()
            logger.info("[ConfigService] Config reset to defaults")
            return True
        except Exception as e:
            logger.error(f"[ConfigService] Error resetting config: {e}")
            return False

    def save_account_state(self, account_state: Dict[str, Any]) -> bool:
        """
        Speichert AccountService State (inkl. Positionen) in Config

        Args:
            account_state: Dict von AccountService.to_dict()

        Returns:
            True wenn erfolgreich
        """
        try:
            self.config["account_state"] = account_state
            self._save_config(self.config)

            # Log Positions Count
            ai_positions = len(account_state.get('ai_account', {}).get('active_positions', {}))
            user_positions = len(account_state.get('user_account', {}).get('active_positions', {}))
            logger.info(f"[ConfigService] Account State saved - AI: {ai_positions} positions, User: {user_positions} positions")

            return True
        except Exception as e:
            logger.error(f"[ConfigService] Error saving account state: {e}")
            return False

    def load_account_state(self) -> Optional[Dict[str, Any]]:
        """
        Lädt AccountService State aus Config

        Returns:
            Dict mit account_state oder None wenn nicht vorhanden
        """
        account_state = self.config.get("account_state")

        if account_state:
            ai_positions = len(account_state.get('ai_account', {}).get('active_positions', {}))
            user_positions = len(account_state.get('user_account', {}).get('active_positions', {}))
            logger.info(f"[ConfigService] Account State loaded - AI: {ai_positions} positions, User: {user_positions} positions")
        else:
            logger.info("[ConfigService] No account state found in config")

        return account_state
