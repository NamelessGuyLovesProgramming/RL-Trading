"""
ML Operations API Router
FastAPI endpoints for model training, loading, and management
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from model_metadata import ModelMetadata
from training_manager import TrainingManager


# API Models
class TrainRequest(BaseModel):
    model_name: str
    total_steps: int = 50000
    train_ratio: float = 0.7
    learning_rate: float = 0.0003
    n_steps: int = 64
    batch_size: int = 64  # FIX: Must match n_steps to avoid PPO batch-splitting bug


class LoadModelRequest(BaseModel):
    model_name: str


# Global instances (initialized by chart_server.py)
training_manager: Optional[TrainingManager] = None
rl_agent: Optional[Any] = None


def set_training_manager(manager: TrainingManager):
    """Set the global training manager instance"""
    global training_manager
    training_manager = manager


def set_rl_agent(agent: Any):
    """Set the global RL agent instance for hot-reloading models"""
    global rl_agent
    rl_agent = agent


# Create router
router = APIRouter(prefix="/api/ml", tags=["ML Operations"])


@router.get("/models")
async def list_models():
    """
    List all available models with metadata

    Returns:
        {
            "models": [
                {
                    "name": "strategy_v1",
                    "created_at": "2024-11-09T04:30:00",
                    "total_steps": 50000,
                    "train_return": 0.0545,
                    "test_return": 0.021,
                    "overfitting_score": 0.15,
                    ...
                }
            ],
            "current_model": "strategy_v1"
        }
    """
    models_dir = Path("models")

    if not models_dir.exists():
        return {"models": [], "current_model": None}

    # List all models with metadata
    model_names = ModelMetadata.list_models(models_dir)
    models = []

    for name in model_names:
        try:
            metadata = ModelMetadata.load(name, models_dir)
            models.append(metadata.get_summary())
        except Exception as e:
            print(f"[ML API] Error loading metadata for {name}: {e}")

    # Get current loaded model (from chart server state)
    # TODO: Get from global state
    current_model = None

    return {
        "models": models,
        "current_model": current_model
    }


@router.get("/models/{model_name}")
async def get_model_metadata(model_name: str):
    """
    Get detailed metadata for a specific model

    Returns:
        Full ModelMetadata dict
    """
    models_dir = Path("models")

    try:
        metadata = ModelMetadata.load(model_name, models_dir)
        return {"success": True, "metadata": metadata.to_dict()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def start_training(request: TrainRequest):
    """
    Start a new training job

    Request:
        {
            "model_name": "strategy_v2",
            "total_steps": 50000,
            "train_ratio": 0.7,
            ...
        }

    Returns:
        {
            "status": "started",
            "job_id": "train_20241109_043000",
            "message": "Training started..."
        }
    """
    if not training_manager:
        raise HTTPException(status_code=500, detail="Training manager not initialized")

    # Check if model already exists
    models_dir = Path("models")
    model_path = models_dir / f"{request.model_name}.zip"

    if model_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Model '{request.model_name}' already exists. Choose a different name."
        )

    # Start training job
    try:
        job_id = training_manager.start_training(
            model_name=request.model_name,
            total_steps=request.total_steps,
            train_ratio=request.train_ratio,
            learning_rate=request.learning_rate,
            n_steps=request.n_steps,
            batch_size=request.batch_size
        )

        # Estimate duration (rough estimate: 1000 steps ≈ 2 minutes)
        estimated_duration = (request.total_steps / 1000) * 120

        return {
            "status": "started",
            "job_id": job_id,
            "model_name": request.model_name,
            "estimated_duration_seconds": estimated_duration,
            "message": "Training started in background. Listen to WebSocket for progress updates."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start training: {str(e)}")


@router.get("/jobs")
async def list_jobs():
    """
    List all training jobs

    Returns:
        {
            "jobs": [
                {
                    "job_id": "train_20241109_043000",
                    "model_name": "strategy_v2",
                    "status": "running",
                    "progress": 0.5,
                    ...
                }
            ]
        }
    """
    if not training_manager:
        raise HTTPException(status_code=500, detail="Training manager not initialized")

    jobs = training_manager.list_jobs()
    return {"jobs": jobs}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of a specific training job

    Returns:
        {
            "job_id": "train_20241109_043000",
            "model_name": "strategy_v2",
            "status": "running",
            "start_time": "2024-11-09T04:30:00",
            "is_running": true,
            "last_progress": {...},
            "error": null
        }
    """
    if not training_manager:
        raise HTTPException(status_code=500, detail="Training manager not initialized")

    status = training_manager.get_job_status(job_id)

    if not status:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return status


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    """
    Stop a running training job

    Returns:
        {
            "success": true,
            "message": "Job stopped"
        }
    """
    if not training_manager:
        raise HTTPException(status_code=500, detail="Training manager not initialized")

    success = training_manager.stop_job(job_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found or already stopped")

    return {
        "success": True,
        "message": f"Job '{job_id}' stopped successfully"
    }


@router.post("/load_model")
async def load_model(request: LoadModelRequest):
    """
    Load a model (hot-swap without server restart)

    Returns:
        {
            "success": true,
            "model_name": "strategy_v1",
            "message": "Model loaded successfully"
        }
    """
    if not rl_agent:
        raise HTTPException(status_code=500, detail="RL agent not initialized")

    models_dir = Path("models")
    model_path = models_dir / f"{request.model_name}.zip"

    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Model '{request.model_name}' not found")

    try:
        # Load metadata to verify
        metadata = ModelMetadata.load(request.model_name, models_dir)

        # Hot-reload RL agent
        from stable_baselines3 import PPO
        rl_agent.model = PPO.load(str(model_path))
        rl_agent.mode = 'ppo'

        print(f"[ML API] ✅ Model '{request.model_name}' loaded successfully")

        return {
            "success": True,
            "model_name": request.model_name,
            "metadata": metadata.get_summary(),
            "message": "Model loaded successfully. AI mode will use this model."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")


@router.delete("/models/{model_name}")
async def delete_model(model_name: str):
    """
    Delete a model and all its files

    Returns:
        {
            "success": true,
            "message": "Model deleted successfully"
        }
    """
    import os

    models_dir = Path("models")
    model_path = models_dir / f"{model_name}.zip"
    metadata_path = models_dir / f"{model_name}_metadata.json"
    data_path = models_dir / f"{model_name}_data.pkl"

    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    try:
        # Delete all model files
        deleted_files = []

        if model_path.exists():
            os.remove(model_path)
            deleted_files.append(str(model_path))

        if metadata_path.exists():
            os.remove(metadata_path)
            deleted_files.append(str(metadata_path))

        if data_path.exists():
            os.remove(data_path)
            deleted_files.append(str(data_path))

        print(f"[ML API] 🗑️ Deleted model '{model_name}': {len(deleted_files)} files")

        return {
            "success": True,
            "model_name": model_name,
            "deleted_files": deleted_files,
            "message": f"Model '{model_name}' deleted successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")


@router.post("/cleanup")
async def cleanup_jobs():
    """
    Cleanup completed/failed jobs from memory

    Returns:
        {
            "cleaned": 5,
            "message": "Cleaned up 5 completed jobs"
        }
    """
    if not training_manager:
        raise HTTPException(status_code=500, detail="Training manager not initialized")

    cleaned = training_manager.cleanup_completed_jobs()

    return {
        "cleaned": cleaned,
        "message": f"Cleaned up {cleaned} completed jobs"
    }
