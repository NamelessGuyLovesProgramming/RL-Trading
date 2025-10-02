"""
Unit Tests für StateRepository
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from charts.repositories.state_repository import StateRepository


class TestStateRepository:
    """Test Suite für StateRepository"""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Fixture für temporäre State-Datei"""
        return tmp_path / "test_state.json"

    @pytest.fixture
    def state_repo(self, temp_state_file):
        """Fixture für StateRepository mit temp file"""
        return StateRepository(state_file=str(temp_state_file))

    def test_initialization(self, state_repo, temp_state_file):
        """Test: StateRepository-Initialisierung"""
        assert state_repo is not None
        assert state_repo.state_file == temp_state_file
        assert state_repo.backup_file == Path(str(temp_state_file) + ".backup")

    def test_save_state(self, state_repo):
        """Test: State speichern"""
        test_state = {
            'current_timeframe': '5m',
            'current_date': '2024-01-15',
            'chart_position': 100
        }

        result = state_repo.save_state(test_state)

        assert result is True
        assert state_repo.state_file.exists()

    def test_load_state(self, state_repo):
        """Test: State laden"""
        # State speichern
        test_state = {
            'current_timeframe': '5m',
            'current_date': '2024-01-15',
            'debug_mode': False
        }
        state_repo.save_state(test_state)

        # State laden
        loaded_state = state_repo.load_state()

        assert loaded_state is not None
        assert loaded_state['current_timeframe'] == '5m'
        assert loaded_state['current_date'] == '2024-01-15'
        assert loaded_state['debug_mode'] is False

    def test_load_nonexistent_state(self, state_repo):
        """Test: Nicht existierenden State laden"""
        result = state_repo.load_state()

        # Sollte None zurückgeben
        assert result is None

    def test_backup_creation(self, state_repo):
        """Test: Backup-Erstellung bei erneutem Speichern"""
        # Ersten State speichern
        state_1 = {'version': 1}
        state_repo.save_state(state_1)

        # Zweiten State speichern (sollte Backup erstellen)
        state_2 = {'version': 2}
        state_repo.save_state(state_2)

        # Backup sollte existieren
        assert state_repo.backup_file.exists()

        # Geladener State sollte Version 2 sein
        loaded = state_repo.load_state()
        assert loaded['version'] == 2

    def test_backup_restoration(self, state_repo):
        """Test: Backup-Wiederherstellung bei korrupter State-Datei"""
        # State und Backup erstellen
        state_1 = {'version': 1}
        state_repo.save_state(state_1)

        state_2 = {'version': 2}
        state_repo.save_state(state_2)

        # State-Datei korrupt machen (ungültiges JSON)
        with open(state_repo.state_file, 'w') as f:
            f.write("INVALID JSON{{{")

        # Sollte auf Backup zurückfallen
        loaded = state_repo.load_state()

        # Backup sollte geladen werden
        # (In diesem Fall haben wir version 1 im Backup)
        assert loaded is not None

    def test_delete_state(self, state_repo):
        """Test: State löschen"""
        # State erstellen
        test_state = {'test': 'data'}
        state_repo.save_state(test_state)

        assert state_repo.state_file.exists()

        # Löschen
        result = state_repo.delete_state()

        assert result is True
        assert not state_repo.state_file.exists()
        assert not state_repo.backup_file.exists()

    def test_delete_nonexistent_state(self, state_repo):
        """Test: Nicht existierenden State löschen"""
        result = state_repo.delete_state()

        # Sollte False zurückgeben (kein State zum Löschen)
        assert result is False

    def test_state_exists(self, state_repo):
        """Test: State-Existenz prüfen"""
        # Initial sollte kein State existieren
        assert not state_repo.state_exists()

        # State erstellen
        state_repo.save_state({'test': 'data'})

        # Jetzt sollte State existieren
        assert state_repo.state_exists()

    def test_get_state_info(self, state_repo):
        """Test: State-Info abrufen"""
        # State erstellen
        test_state = {'test': 'data'}
        state_repo.save_state(test_state)

        # Info abrufen
        info = state_repo.get_state_info()

        assert info['state_file_exists'] is True
        assert 'state_file_path' in info
        assert 'state_file_size' in info
        assert 'state_file_modified' in info

    def test_validate_state(self, state_repo):
        """Test: State-Validierung"""
        # Gültiger State
        valid_state = {
            'timestamp': '2024-01-15T10:00:00',
            'version': '2.0.0',
            'state': {'test': 'data'}
        }
        assert state_repo._validate_state(valid_state) is True

        # Ungültiger State (fehlendes 'state')
        invalid_state_1 = {
            'timestamp': '2024-01-15T10:00:00',
            'version': '2.0.0'
        }
        assert state_repo._validate_state(invalid_state_1) is False

        # Ungültiger State (fehlendes 'timestamp')
        invalid_state_2 = {
            'version': '2.0.0',
            'state': {'test': 'data'}
        }
        assert state_repo._validate_state(invalid_state_2) is False

        # Ungültiger State (kein dict)
        assert state_repo._validate_state("not a dict") is False

    def test_json_serializer(self, state_repo):
        """Test: Custom JSON Serializer"""
        # datetime Objekt sollte zu ISO-String konvertiert werden
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = StateRepository._json_serializer(dt)
        assert isinstance(result, str)
        assert "2024-01-15" in result

        # Objekt mit __dict__ sollte zu dict konvertiert werden
        class TestObj:
            def __init__(self):
                self.value = 42

        obj = TestObj()
        result = StateRepository._json_serializer(obj)
        assert isinstance(result, dict)
        assert result['value'] == 42

        # Andere Objekte sollten zu String konvertiert werden
        result = StateRepository._json_serializer(123)
        assert isinstance(result, str)

    def test_save_state_with_datetime(self, state_repo):
        """Test: State mit datetime-Objekten speichern"""
        test_state = {
            'timestamp': datetime(2024, 1, 15, 10, 30),
            'data': 'test'
        }

        # Sollte ohne Fehler speichern (datetime wird serialisiert)
        result = state_repo.save_state(test_state)
        assert result is True

        # Laden und prüfen
        loaded = state_repo.load_state()
        assert loaded is not None
        assert loaded['data'] == 'test'
        # datetime wurde zu String konvertiert
        assert isinstance(loaded['timestamp'], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
