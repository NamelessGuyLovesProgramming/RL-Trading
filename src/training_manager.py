"""
Training Manager
Manages background training processes and streams progress
"""

import subprocess
import json
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import sys


class TrainingJob:
    """Represents a running training job"""

    def __init__(
        self,
        job_id: str,
        model_name: str,
        process: subprocess.Popen,
        config: Dict[str, Any]
    ):
        self.job_id = job_id
        self.model_name = model_name
        self.process = process
        self.config = config
        self.start_time = datetime.now()
        self.status = "running"
        self.last_progress = {}
        self.error = None

    def is_running(self) -> bool:
        """Check if process is still running"""
        return self.process.poll() is None

    def kill(self):
        """Kill the training process"""
        if self.is_running():
            self.process.kill()
            self.status = "killed"


class TrainingManager:
    """
    Manages background training processes

    Features:
    - Spawn training worker as subprocess
    - Monitor stdout for JSON progress messages
    - Broadcast updates via callback
    - Cleanup on completion/error
    """

    def __init__(self, websocket_broadcast: Optional[Callable] = None):
        """
        Args:
            websocket_broadcast: Async function to broadcast messages
        """
        self.jobs: Dict[str, TrainingJob] = {}
        self.websocket_broadcast = websocket_broadcast

    def start_training(
        self,
        model_name: str,
        total_steps: int = 50000,
        train_ratio: float = 0.7,
        learning_rate: float = 0.0003,
        n_steps: int = 64,
        batch_size: int = 64  # FIX: Match n_steps to avoid batch-splitting bug
    ) -> str:
        """
        Start a new training job

        Returns:
            job_id: Unique job identifier
        """
        job_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Build command
        cmd = [
            sys.executable,  # python interpreter
            "src/train_worker.py",
            "--name", model_name,
            "--steps", str(total_steps),
            "--train-ratio", str(train_ratio),
            "--lr", str(learning_rate),
            "--n-steps", str(n_steps),
            "--batch-size", str(batch_size)
        ]

        print(f"[TrainingManager] Starting training: {model_name}")
        print(f"[TrainingManager] Command: {' '.join(cmd)}")

        # Start subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        # Create job
        job = TrainingJob(
            job_id=job_id,
            model_name=model_name,
            process=process,
            config={
                "total_steps": total_steps,
                "train_ratio": train_ratio,
                "learning_rate": learning_rate,
                "n_steps": n_steps,
                "batch_size": batch_size
            }
        )

        self.jobs[job_id] = job

        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitor_job,
            args=(job_id,),
            daemon=True
        )
        monitor_thread.start()

        print(f"[TrainingManager] Job started: {job_id}")

        return job_id

    def _monitor_job(self, job_id: str):
        """
        Monitor job stdout for progress messages

        Runs in background thread, parses JSON, broadcasts updates
        """
        job = self.jobs.get(job_id)
        if not job:
            return

        print(f"[TrainingManager] Monitoring job: {job_id}")

        try:
            # Read stdout line by line
            for line in job.process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Parse JSON message
                    message = json.loads(line)

                    # Store last progress
                    job.last_progress = message

                    # Broadcast to WebSocket clients
                    self._broadcast_progress(job_id, message)

                    # Check for completion
                    if message.get("type") == "completed":
                        job.status = "completed"
                        print(f"[TrainingManager] Job completed: {job_id}")

                    # Check for error
                    elif message.get("type") == "error":
                        job.status = "error"
                        job.error = message.get("error")
                        print(f"[TrainingManager] Job error: {job_id} - {job.error}")

                except json.JSONDecodeError:
                    # Non-JSON output (e.g., warnings, debug prints)
                    print(f"[TrainingWorker] {line}")

            # Wait for process to finish
            return_code = job.process.wait()

            if return_code != 0 and job.status != "completed":
                job.status = "error"
                stderr = job.process.stderr.read()
                job.error = f"Process exited with code {return_code}: {stderr}"
                print(f"[TrainingManager] Job failed: {job_id}")

                # Broadcast error
                self._broadcast_progress(job_id, {
                    "type": "error",
                    "error": job.error
                })

        except Exception as e:
            job.status = "error"
            job.error = str(e)
            print(f"[TrainingManager] Monitoring error: {job_id} - {e}")

            self._broadcast_progress(job_id, {
                "type": "error",
                "error": str(e)
            })

    def _broadcast_progress(self, job_id: str, message: Dict[str, Any]):
        """
        Broadcast progress message via WebSocket

        Adds job_id to message and calls async broadcast callback
        """
        if not self.websocket_broadcast:
            return

        message["job_id"] = job_id

        # Call async broadcast in event loop
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Schedule broadcast
            asyncio.run_coroutine_threadsafe(
                self.websocket_broadcast(message),
                loop
            )
        except Exception as e:
            print(f"[TrainingManager] Broadcast error: {e}")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a job"""
        job = self.jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "model_name": job.model_name,
            "status": job.status,
            "start_time": job.start_time.isoformat(),
            "is_running": job.is_running(),
            "last_progress": job.last_progress,
            "error": job.error,
            "config": job.config
        }

    def list_jobs(self) -> list[Dict[str, Any]]:
        """List all jobs"""
        return [self.get_job_status(job_id) for job_id in self.jobs.keys()]

    def stop_job(self, job_id: str) -> bool:
        """Stop a running job"""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.is_running():
            job.kill()
            print(f"[TrainingManager] Job stopped: {job_id}")
            return True

        return False

    def cleanup_completed_jobs(self):
        """Remove completed/failed jobs from memory"""
        completed = [
            job_id for job_id, job in self.jobs.items()
            if job.status in ["completed", "error", "killed"] and not job.is_running()
        ]

        for job_id in completed:
            del self.jobs[job_id]
            print(f"[TrainingManager] Cleaned up job: {job_id}")

        return len(completed)


# Example Usage / Testing
if __name__ == "__main__":
    import time

    print("="*60)
    print("TRAINING MANAGER TEST")
    print("="*60)

    # Create manager
    manager = TrainingManager()

    # Start a quick training job (1000 steps)
    job_id = manager.start_training(
        model_name="test_model",
        total_steps=1000,
        train_ratio=0.7
    )

    print(f"\n[TEST] Job started: {job_id}")
    print("[TEST] Monitoring progress...\n")

    # Monitor progress
    while True:
        status = manager.get_job_status(job_id)

        if not status:
            print("[TEST] Job not found")
            break

        print(f"\r[TEST] Status: {status['status']} | Running: {status['is_running']}", end="")

        if status['status'] in ['completed', 'error']:
            print(f"\n\n[TEST] Final status: {status['status']}")
            if status['error']:
                print(f"[TEST] Error: {status['error']}")
            break

        time.sleep(2)

    print("\n" + "="*60)
    print("TEST COMPLETED")
    print("="*60)
