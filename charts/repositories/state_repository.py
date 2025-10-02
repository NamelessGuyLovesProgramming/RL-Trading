"""
State Repository - Persistierung von Anwendungs-State
Speichert und lädt Anwendungs-Zustand für Session-Wiederherstellung
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class StateRepository:
    """
    Repository für State-Persistierung

    Verantwortlichkeiten:
    - Speichern von Anwendungs-State in JSON
    - Laden von persistiertem State
    - State-Validierung
    - Backup-Management
    """

    def __init__(self, state_file: str = "chart_state.json"):
        """
        Initialisiert State Repository

        Args:
            state_file: Pfad zur State-Datei
        """
        self.state_file = Path(state_file)
        self.backup_file = Path(f"{state_file}.backup")
        print(f"[StateRepository] Initialisiert mit state_file: {self.state_file}")

    def save_state(self, state: Dict[str, Any]) -> bool:
        """
        Speichert State in JSON-Datei

        Args:
            state: State-Dictionary zum Speichern

        Returns:
            True wenn erfolgreich gespeichert
        """
        try:
            # Backup des alten State erstellen (falls vorhanden)
            if self.state_file.exists():
                self.state_file.replace(self.backup_file)
                print(f"[StateRepository] Backup erstellt: {self.backup_file}")

            # State mit Metadaten erweitern
            state_with_meta = {
                'timestamp': datetime.now().isoformat(),
                'version': '2.0.0',
                'state': state
            }

            # State speichern
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_with_meta, f, indent=2, default=self._json_serializer)

            print(f"[StateRepository] State gespeichert: {self.state_file}")
            return True

        except Exception as e:
            print(f"[StateRepository] ERROR beim Speichern: {e}")
            # Bei Fehler: Backup wiederherstellen
            if self.backup_file.exists():
                self.backup_file.replace(self.state_file)
                print(f"[StateRepository] Backup wiederhergestellt")
            return False

    def load_state(self) -> Optional[Dict[str, Any]]:
        """
        Lädt State aus JSON-Datei

        Returns:
            State-Dictionary oder None bei Fehler
        """
        # Versuche State-Datei zu laden
        state = self._load_from_file(self.state_file)

        if state is not None:
            return state

        # Fallback: Versuche Backup
        print("[StateRepository] State-Datei nicht gefunden, versuche Backup...")
        state = self._load_from_file(self.backup_file)

        if state is not None:
            # Backup wiederherstellen
            self.backup_file.replace(self.state_file)
            print("[StateRepository] Backup als State wiederhergestellt")
            return state

        print("[StateRepository] Kein State verfügbar (weder primary noch backup)")
        return None

    def _load_from_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Lädt State aus spezifischer Datei

        Args:
            file_path: Pfad zur State-Datei

        Returns:
            State-Dictionary oder None
        """
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state_with_meta = json.load(f)

            # Validierung
            if not self._validate_state(state_with_meta):
                print(f"[StateRepository] State-Validierung fehlgeschlagen: {file_path}")
                return None

            # Extrahiere eigentlichen State
            state = state_with_meta.get('state', {})

            timestamp = state_with_meta.get('timestamp', 'unknown')
            version = state_with_meta.get('version', 'unknown')
            print(f"[StateRepository] State geladen: {file_path} (v{version}, {timestamp})")

            return state

        except json.JSONDecodeError as e:
            print(f"[StateRepository] JSON-Fehler beim Laden von {file_path}: {e}")
            return None
        except Exception as e:
            print(f"[StateRepository] ERROR beim Laden von {file_path}: {e}")
            return None

    def _validate_state(self, state_with_meta: Dict[str, Any]) -> bool:
        """
        Validiert State-Struktur

        Args:
            state_with_meta: State mit Metadaten

        Returns:
            True wenn valide
        """
        # Basis-Validierung
        if not isinstance(state_with_meta, dict):
            return False

        if 'state' not in state_with_meta:
            return False

        if 'timestamp' not in state_with_meta:
            return False

        # Optional: Version-Check
        version = state_with_meta.get('version', '1.0.0')
        # Für zukünftige Kompatibilitäts-Checks

        return True

    def delete_state(self) -> bool:
        """
        Löscht persistierten State

        Returns:
            True wenn erfolgreich gelöscht
        """
        try:
            deleted_count = 0

            if self.state_file.exists():
                self.state_file.unlink()
                deleted_count += 1

            if self.backup_file.exists():
                self.backup_file.unlink()
                deleted_count += 1

            if deleted_count > 0:
                print(f"[StateRepository] State gelöscht ({deleted_count} Dateien)")
                return True
            else:
                print("[StateRepository] Kein State zum Löschen vorhanden")
                return False

        except Exception as e:
            print(f"[StateRepository] ERROR beim Löschen: {e}")
            return False

    def state_exists(self) -> bool:
        """
        Prüft ob State-Datei existiert

        Returns:
            True wenn State vorhanden
        """
        return self.state_file.exists() or self.backup_file.exists()

    def get_state_info(self) -> Dict[str, Any]:
        """
        Gibt Informationen über persistierten State

        Returns:
            Dictionary mit State-Informationen
        """
        info = {
            'state_file_exists': self.state_file.exists(),
            'backup_file_exists': self.backup_file.exists(),
            'state_file_path': str(self.state_file),
            'backup_file_path': str(self.backup_file)
        }

        # State-Datei Info
        if self.state_file.exists():
            stat = self.state_file.stat()
            info['state_file_size'] = stat.st_size
            info['state_file_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()

        # Backup-Datei Info
        if self.backup_file.exists():
            stat = self.backup_file.stat()
            info['backup_file_size'] = stat.st_size
            info['backup_file_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return info

    @staticmethod
    def _json_serializer(obj):
        """
        Custom JSON Serializer für nicht-standard Typen

        Args:
            obj: Zu serialisierendes Objekt

        Returns:
            Serialisierter Wert
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # Objekte mit __dict__ zu Dictionary konvertieren
            return obj.__dict__
        else:
            return str(obj)
