"""
Model Metadata Management
Speichert Performance-Metriken für trainierte RL Models
"""

from dataclasses import dataclass, asdict
from pathlib import Path
import json
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class TrainingConfig:
    """Training Hyperparameter Configuration"""
    total_steps: int
    learning_rate: float
    n_steps: int
    batch_size: int


@dataclass
class DataSplit:
    """Train/Test Split Information"""
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_candles: int
    test_candles: int


@dataclass
class Performance:
    """Performance Metrics"""
    final_balance: float
    initial_balance: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    max_drawdown: float


class ModelMetadata:
    """
    Model Metadata Manager

    Speichert und lädt Metadaten für trainierte PPO Models
    Ermöglicht Model-Vergleich und Overfitting-Detection
    """

    def __init__(
        self,
        model_name: str,
        training_config: TrainingConfig,
        data_split: DataSplit,
        train_performance: Performance,
        test_performance: Optional[Performance] = None,
        env_config: Optional[Dict[str, Any]] = None
    ):
        self.model_name = model_name
        self.created_at = datetime.now().isoformat()
        self.training_config = training_config
        self.data_split = data_split
        self.train_performance = train_performance
        self.test_performance = test_performance
        self.env_config = env_config or {}
        self.version = "1.0"

        # Calculate overfitting score
        self.overfitting_score = self._calculate_overfitting()

    def _calculate_overfitting(self) -> Optional[float]:
        """
        Berechnet Overfitting Score

        Score = (train_return - test_return) / train_return

        0.0 = Perfect (same performance)
        0.5 = Moderate overfitting
        1.0 = Extreme overfitting (test return = 0)
        """
        if not self.test_performance:
            return None

        train_return = self.train_performance.total_return
        test_return = self.test_performance.total_return

        if train_return <= 0:
            return None

        return (train_return - test_return) / train_return

    def save(self, models_dir: Path = Path("models")) -> Path:
        """
        Save metadata to JSON file

        Args:
            models_dir: Directory where models are stored

        Returns:
            Path to saved metadata file
        """
        models_dir.mkdir(parents=True, exist_ok=True)
        filepath = models_dir / f"{self.model_name}.metadata.json"

        data = {
            "model_name": self.model_name,
            "created_at": self.created_at,
            "training_config": asdict(self.training_config),
            "data_split": asdict(self.data_split),
            "train_performance": asdict(self.train_performance),
            "test_performance": asdict(self.test_performance) if self.test_performance else None,
            "overfitting_score": self.overfitting_score,
            "env_config": self.env_config,
            "version": self.version
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"[ModelMetadata] Saved to: {filepath}")
        return filepath

    @classmethod
    def load(cls, model_name: str, models_dir: Path = Path("models")) -> 'ModelMetadata':
        """
        Load metadata from JSON file

        Args:
            model_name: Name of the model
            models_dir: Directory where models are stored

        Returns:
            ModelMetadata instance
        """
        filepath = models_dir / f"{model_name}.metadata.json"

        if not filepath.exists():
            raise FileNotFoundError(f"Metadata not found: {filepath}")

        with open(filepath, 'r') as f:
            data = json.load(f)

        metadata = cls(
            model_name=data['model_name'],
            training_config=TrainingConfig(**data['training_config']),
            data_split=DataSplit(**data['data_split']),
            train_performance=Performance(**data['train_performance']),
            test_performance=Performance(**data['test_performance']) if data.get('test_performance') else None,
            env_config=data.get('env_config', {})
        )

        # Restore original created_at timestamp
        metadata.created_at = data['created_at']

        print(f"[ModelMetadata] Loaded from: {filepath}")
        return metadata

    @staticmethod
    def list_models(models_dir: Path = Path("models")) -> list[str]:
        """
        List all models with metadata

        Args:
            models_dir: Directory where models are stored

        Returns:
            List of model names
        """
        if not models_dir.exists():
            return []

        metadata_files = list(models_dir.glob("*.metadata.json"))
        model_names = [f.stem.replace(".metadata", "") for f in metadata_files]

        return sorted(model_names)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "model_name": self.model_name,
            "created_at": self.created_at,
            "training_config": asdict(self.training_config),
            "data_split": asdict(self.data_split),
            "train_performance": asdict(self.train_performance),
            "test_performance": asdict(self.test_performance) if self.test_performance else None,
            "overfitting_score": self.overfitting_score,
            "env_config": self.env_config,
            "version": self.version
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get compact summary for UI"""
        return {
            "name": self.model_name,
            "created_at": self.created_at,
            "total_steps": self.training_config.total_steps,
            "train_return": self.train_performance.total_return,
            "test_return": self.test_performance.total_return if self.test_performance else None,
            "overfitting_score": self.overfitting_score,
            "train_win_rate": self.train_performance.win_rate,
            "test_win_rate": self.test_performance.win_rate if self.test_performance else None,
        }


# Example Usage
if __name__ == "__main__":
    # Create metadata for a trained model
    metadata = ModelMetadata(
        model_name="strategy_v1",
        training_config=TrainingConfig(
            total_steps=50000,
            learning_rate=0.0003,
            n_steps=64,
            batch_size=32
        ),
        data_split=DataSplit(
            train_start="2024-01-01",
            train_end="2024-09-15",
            test_start="2024-09-16",
            test_end="2024-12-31",
            train_candles=49702,
            test_candles=21301
        ),
        train_performance=Performance(
            final_balance=105450.0,
            initial_balance=100000.0,
            total_return=0.0545,
            total_trades=234,
            winning_trades=152,
            losing_trades=82,
            win_rate=0.6496,
            avg_win=450.23,
            avg_loss=-230.45,
            max_drawdown=0.0234
        ),
        test_performance=Performance(
            final_balance=102100.0,
            initial_balance=100000.0,
            total_return=0.021,
            total_trades=98,
            winning_trades=59,
            losing_trades=39,
            win_rate=0.6020,
            avg_win=420.15,
            avg_loss=-245.67,
            max_drawdown=0.0312
        )
    )

    # Save metadata
    metadata.save()

    # Load metadata
    loaded = ModelMetadata.load("strategy_v1")

    print("\n[TEST] Metadata Summary:")
    print(json.dumps(loaded.get_summary(), indent=2))

    print(f"\nOverfitting Score: {loaded.overfitting_score:.2%}")

    print("\n✅ Model Metadata System works!")
