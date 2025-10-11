"""
Unit Tests für charts.core.transaction
Testet EventBasedTransaction
"""

import pytest
from datetime import datetime
from charts.core.transaction import EventBasedTransaction


class TestEventBasedTransaction:
    """Tests für EventBasedTransaction"""

    @pytest.fixture
    def transaction(self):
        """Erstellt Transaction Instanz"""
        return EventBasedTransaction()

    @pytest.fixture
    def sample_skip_events(self):
        """Erstellt Sample Skip Events"""
        return [
            {
                'time': datetime(2024, 1, 1, 0, 0),
                'candle': {'time': 1704067200, 'open': 20000.0, 'high': 20010.0, 'low': 19990.0, 'close': 20005.0},
                'original_timeframe': '5m'
            },
            {
                'time': datetime(2024, 1, 1, 0, 5),
                'candle': {'time': 1704067500, 'open': 20005.0, 'high': 20015.0, 'low': 19995.0, 'close': 20010.0},
                'original_timeframe': '5m'
            }
        ]

    # === INITIALIZATION TESTS ===

    def test_transaction_initialization(self, transaction):
        """Test: Transaction wird korrekt initialisiert"""
        assert transaction.backup_events == []
        assert transaction.is_active is False
        assert transaction.transaction_id is None

    # === BEGIN TRANSACTION TESTS ===

    def test_begin_transaction(self, transaction, sample_skip_events):
        """Test: Transaction wird gestartet und Events werden gebackupt"""
        tx_id = transaction.begin_transaction(sample_skip_events)

        assert transaction.is_active is True
        assert transaction.transaction_id == tx_id
        assert len(transaction.backup_events) == len(sample_skip_events)

    def test_begin_transaction_with_custom_id(self, transaction, sample_skip_events):
        """Test: Transaction mit custom ID"""
        custom_id = "custom_tx_123"
        tx_id = transaction.begin_transaction(sample_skip_events, transaction_id=custom_id)

        assert tx_id == custom_id
        assert transaction.transaction_id == custom_id

    def test_begin_transaction_creates_backup(self, transaction, sample_skip_events):
        """Test: Begin erstellt Backup-Kopie (nicht Referenz)"""
        tx_id = transaction.begin_transaction(sample_skip_events)

        # Backup sollte Kopie sein, nicht Referenz
        assert transaction.backup_events is not sample_skip_events
        assert len(transaction.backup_events) == len(sample_skip_events)

    # === COMMIT TRANSACTION TESTS ===

    def test_commit_transaction_success(self, transaction, sample_skip_events):
        """Test: Transaction wird erfolgreich committed"""
        transaction.begin_transaction(sample_skip_events)

        result = transaction.commit_transaction(sample_skip_events)

        assert result is True
        assert transaction.is_active is False
        assert transaction.transaction_id is None
        assert transaction.backup_events == []

    def test_commit_transaction_without_begin(self, transaction, sample_skip_events):
        """Test: Commit ohne aktive Transaction gibt Warning"""
        result = transaction.commit_transaction(sample_skip_events)

        assert result is False

    # === ROLLBACK TRANSACTION TESTS ===

    def test_rollback_transaction_restores_backup(self, transaction, sample_skip_events):
        """Test: Rollback stellt Backup wieder her"""
        # Start transaction und backup
        transaction.begin_transaction(sample_skip_events)

        # Modifiziere Events
        sample_skip_events.clear()
        sample_skip_events.append({'modified': True})

        # Rollback
        result = transaction.rollback_transaction(sample_skip_events, reason="Test rollback")

        assert result is True
        assert len(sample_skip_events) == 2  # Original 2 events restored
        assert 'modified' not in str(sample_skip_events)

    def test_rollback_transaction_without_begin(self, transaction, sample_skip_events):
        """Test: Rollback ohne aktive Transaction gibt Warning"""
        result = transaction.rollback_transaction(sample_skip_events, reason="Test")

        assert result is False

    def test_rollback_transaction_clears_state(self, transaction, sample_skip_events):
        """Test: Rollback räumt Transaction State auf"""
        transaction.begin_transaction(sample_skip_events)
        transaction.rollback_transaction(sample_skip_events)

        assert transaction.is_active is False
        assert transaction.transaction_id is None
        assert transaction.backup_events == []

    # === GET STATUS TESTS ===

    def test_get_status_inactive(self, transaction):
        """Test: Status einer inaktiven Transaction"""
        status = transaction.get_status()

        assert status['is_active'] is False
        assert status['transaction_id'] is None
        assert status['backup_count'] == 0

    def test_get_status_active(self, transaction, sample_skip_events):
        """Test: Status einer aktiven Transaction"""
        tx_id = transaction.begin_transaction(sample_skip_events)
        status = transaction.get_status()

        assert status['is_active'] is True
        assert status['transaction_id'] == tx_id
        assert status['backup_count'] == len(sample_skip_events)

    # === INTEGRATION TESTS ===

    def test_full_commit_workflow(self, transaction, sample_skip_events):
        """Test: Kompletter Commit-Workflow"""
        # Begin
        tx_id = transaction.begin_transaction(sample_skip_events)
        assert transaction.is_active

        # Modify events
        sample_skip_events.append({'added': True})

        # Commit
        result = transaction.commit_transaction(sample_skip_events)
        assert result is True
        assert not transaction.is_active

        # Changes should persist (3 events now)
        assert len(sample_skip_events) == 3

    def test_full_rollback_workflow(self, transaction, sample_skip_events):
        """Test: Kompletter Rollback-Workflow"""
        # Begin
        transaction.begin_transaction(sample_skip_events)

        # Modify events
        original_count = len(sample_skip_events)
        sample_skip_events.append({'should_be_rolled_back': True})

        # Rollback
        transaction.rollback_transaction(sample_skip_events, reason="Test rollback")

        # Changes should be reverted
        assert len(sample_skip_events) == original_count
        assert all('should_be_rolled_back' not in str(e) for e in sample_skip_events)
