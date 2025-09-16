"""
RL Trading Agent mit Human-in-the-Loop Integration
Wrapper für Stable-Baselines3 mit Custom Features
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
import torch
import torch.nn as nn
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.policies import ActorCriticPolicy
import logging
import pickle
from datetime import datetime
import wandb


class TradingFeatureExtractor(nn.Module):
    """
    Custom Feature Extractor für Trading Patterns
    """
    def __init__(self, observation_space, features_dim: int = 128):
        super().__init__()

        # Calculate input dimension
        n_input = observation_space.shape[0]

        # Feature extraction layers
        self.feature_extractor = nn.Sequential(
            nn.Linear(n_input, 64),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, features_dim),
            nn.ReLU()
        )

        self.features_dim = features_dim

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        return self.feature_extractor(observations)


class HumanFeedbackCallback(BaseCallback):
    """
    Callback für Human-in-the-Loop Training
    """
    def __init__(self,
                 feedback_interval: int = 100,
                 auto_feedback: bool = False,
                 verbose: int = 1):
        super().__init__(verbose)

        self.feedback_interval = feedback_interval
        self.auto_feedback = auto_feedback
        self.feedback_history = []
        self.performance_history = []

    def _on_step(self) -> bool:
        # Sammle Performance Daten
        if 'episode' in self.locals:
            episode_reward = self.locals.get('episode_reward', 0)
            self.performance_history.append(episode_reward)

        # Periodisches Feedback
        if self.n_calls % self.feedback_interval == 0:
            self._request_feedback()

        return True

    def _request_feedback(self):
        """Request human feedback"""
        if len(self.performance_history) < 10:
            return

        recent_performance = np.mean(self.performance_history[-10:])

        if self.auto_feedback:
            # Automatisches Feedback basierend auf Performance
            if recent_performance > 0:
                feedback = min(recent_performance / 100, 1.0)  # Cap at 1.0
            else:
                feedback = max(recent_performance / 100, -1.0)  # Cap at -1.0
        else:
            # Manuelles Feedback
            print(f"\n=== FEEDBACK REQUEST ===")
            print(f"Recent average reward: {recent_performance:.2f}")
            print(f"Episode: {self.n_calls // self.feedback_interval}")

            try:
                feedback = float(input("Rate recent performance (-1 to 1): "))
                feedback = max(-1.0, min(1.0, feedback))  # Clamp to [-1, 1]
            except (ValueError, KeyboardInterrupt):
                feedback = 0.0

        # Store feedback
        self.feedback_history.append({
            'step': self.n_calls,
            'feedback': feedback,
            'performance': recent_performance,
            'timestamp': datetime.now()
        })

        # Apply feedback to environment if possible
        if hasattr(self.training_env, 'add_human_feedback'):
            self.training_env.add_human_feedback(feedback)

        if self.verbose > 0:
            print(f"Feedback recorded: {feedback}")


class AdaptiveLearningCallback(BaseCallback):
    """
    Adaptive Learning Rate basierend auf Performance
    """
    def __init__(self,
                 initial_lr: float = 3e-4,
                 min_lr: float = 1e-5,
                 max_lr: float = 1e-3,
                 adaptation_window: int = 100,
                 verbose: int = 1):
        super().__init__(verbose)

        self.initial_lr = initial_lr
        self.min_lr = min_lr
        self.max_lr = max_lr
        self.adaptation_window = adaptation_window

        self.reward_history = []
        self.lr_history = []

    def _on_step(self) -> bool:
        # Sammle Reward
        if 'rewards' in self.locals:
            reward = self.locals['rewards'][0] if isinstance(self.locals['rewards'], list) else self.locals['rewards']
            self.reward_history.append(reward)

        # Adaptiere Learning Rate
        if len(self.reward_history) >= self.adaptation_window:
            recent_rewards = self.reward_history[-self.adaptation_window:]

            # Berechne Trend
            if len(recent_rewards) > 10:
                trend = np.polyfit(range(len(recent_rewards)), recent_rewards, 1)[0]

                # Adjustiere Learning Rate basierend auf Trend
                current_lr = self.model.lr_schedule(self.model._current_progress_remaining)

                if trend > 0:  # Positive trend - reduziere LR für Stabilität
                    new_lr = max(current_lr * 0.95, self.min_lr)
                elif trend < -0.01:  # Negative trend - erhöhe LR
                    new_lr = min(current_lr * 1.05, self.max_lr)
                else:
                    new_lr = current_lr

                # Update Learning Rate
                for param_group in self.model.policy.optimizer.param_groups:
                    param_group['lr'] = new_lr

                self.lr_history.append(new_lr)

                if self.verbose > 0 and len(self.lr_history) % 100 == 0:
                    print(f"Adapted LR: {float(new_lr):.6f}, Trend: {float(trend):.6f}")

        return True


class TradingPPOAgent:
    """
    PPO Agent speziell für Trading mit Human Feedback
    """
    def __init__(self,
                 env,
                 learning_rate: float = 3e-4,
                 n_steps: int = 2048,
                 batch_size: int = 64,
                 n_epochs: int = 10,
                 gamma: float = 0.99,
                 use_wandb: bool = False,
                 wandb_project: str = "rl-trading",
                 model_name: str = "trading_ppo"):

        self.env = env
        self.model_name = model_name
        self.use_wandb = use_wandb

        # Initialize Wandb if enabled
        if use_wandb:
            wandb.init(project=wandb_project, name=model_name)

        # Custom policy mit Feature Extractor
        policy_kwargs = dict(
            features_extractor_class=TradingFeatureExtractor,
            features_extractor_kwargs=dict(features_dim=128),
            net_arch=[dict(pi=[128, 64], vf=[128, 64])]
        )

        # Initialize PPO model
        self.model = PPO(
            "MlpPolicy",
            env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            policy_kwargs=policy_kwargs,
            verbose=1,
            tensorboard_log="./tensorboard_logs/" if not use_wandb else None
        )

        # Callbacks
        self.callbacks = []
        self.setup_callbacks()

        # Training history
        self.training_history = []
        self.episode_rewards = []

        # Logging
        self.logger = logging.getLogger(__name__)

    def setup_callbacks(self):
        """Setup training callbacks"""
        # Human Feedback Callback
        self.human_feedback_callback = HumanFeedbackCallback(
            feedback_interval=500,
            auto_feedback=False
        )
        self.callbacks.append(self.human_feedback_callback)

        # Adaptive Learning Rate Callback
        self.adaptive_lr_callback = AdaptiveLearningCallback(
            initial_lr=self.model.learning_rate
        )
        self.callbacks.append(self.adaptive_lr_callback)

    def train(self,
              total_timesteps: int = 50000,
              feedback_enabled: bool = True,
              save_interval: int = 10000):
        """
        Train the agent with optional human feedback
        """
        self.logger.info(f"Starting training for {total_timesteps} timesteps")

        if feedback_enabled:
            self.logger.info("Human feedback enabled - you'll be asked for feedback periodically")

        try:
            self.model.learn(
                total_timesteps=total_timesteps,
                callback=self.callbacks if feedback_enabled else None,
                log_interval=10
            )

            # Save final model
            self.save_model()

            self.logger.info("Training completed successfully")

        except KeyboardInterrupt:
            self.logger.info("Training interrupted by user")
            self.save_model(suffix="_interrupted")

        except Exception as e:
            self.logger.error(f"Training error: {e}")
            raise

    def predict(self, observation, deterministic: bool = True):
        """Predict action for given observation"""
        return self.model.predict(observation, deterministic=deterministic)

    def evaluate(self, n_episodes: int = 10) -> Dict:
        """Evaluate agent performance"""
        self.logger.info(f"Evaluating agent over {n_episodes} episodes")

        episode_rewards = []
        episode_lengths = []
        win_rates = []

        for episode in range(n_episodes):
            obs, _ = self.env.reset()
            episode_reward = 0
            episode_length = 0
            done = False

            while not done:
                action, _ = self.predict(obs)
                obs, reward, done, _, info = self.env.step(action)
                episode_reward += reward
                episode_length += 1

            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)

            # Extract win rate if available
            win_rate = info.get('win_rate', 0)
            win_rates.append(win_rate)

            self.logger.info(f"Episode {episode + 1}: Reward={episode_reward:.2f}, "
                           f"Length={episode_length}, Win Rate={win_rate:.2%}")

        # Calculate statistics
        eval_stats = {
            'mean_reward': np.mean(episode_rewards),
            'std_reward': np.std(episode_rewards),
            'mean_length': np.mean(episode_lengths),
            'mean_win_rate': np.mean(win_rates),
            'max_reward': np.max(episode_rewards),
            'min_reward': np.min(episode_rewards)
        }

        self.logger.info(f"Evaluation Results: {eval_stats}")

        if self.use_wandb:
            wandb.log(eval_stats)

        return eval_stats

    def save_model(self, suffix: str = ""):
        """Save model and training data"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.model_name}_{timestamp}{suffix}"

        # Save model
        model_path = f"models/{filename}"
        self.model.save(model_path)

        # Save additional data
        training_data = {
            'training_history': self.training_history,
            'episode_rewards': self.episode_rewards,
            'feedback_history': getattr(self.human_feedback_callback, 'feedback_history', []),
            'lr_history': getattr(self.adaptive_lr_callback, 'lr_history', []),
            'model_params': {
                'learning_rate': self.model.learning_rate,
                'n_steps': self.model.n_steps,
                'batch_size': self.model.batch_size,
                'gamma': self.model.gamma
            }
        }

        with open(f"{model_path}_data.pkl", 'wb') as f:
            pickle.dump(training_data, f)

        self.logger.info(f"Model saved as {model_path}")

    def load_model(self, model_path: str):
        """Load saved model"""
        self.model = PPO.load(model_path, env=self.env)

        # Try to load additional data
        try:
            with open(f"{model_path}_data.pkl", 'rb') as f:
                training_data = pickle.load(f)

            self.training_history = training_data.get('training_history', [])
            self.episode_rewards = training_data.get('episode_rewards', [])

            self.logger.info(f"Model loaded from {model_path}")

        except FileNotFoundError:
            self.logger.warning("Additional training data not found")

    def get_training_stats(self) -> Dict:
        """Get training statistics"""
        if not hasattr(self.human_feedback_callback, 'feedback_history'):
            return {}

        feedback_hist = self.human_feedback_callback.feedback_history

        if not feedback_hist:
            return {}

        feedbacks = [f['feedback'] for f in feedback_hist]

        return {
            'total_feedback_points': len(feedbacks),
            'avg_feedback': np.mean(feedbacks),
            'positive_feedback_ratio': sum(1 for f in feedbacks if f > 0) / len(feedbacks),
            'last_feedback': feedbacks[-1] if feedbacks else 0,
            'feedback_trend': np.polyfit(range(len(feedbacks)), feedbacks, 1)[0] if len(feedbacks) > 1 else 0
        }


class TradingSACAgent:
    """
    SAC Agent für kontinuierliche Action Spaces (falls erwünscht)
    """
    def __init__(self, env, **kwargs):
        # Similar structure wie PPO aber für SAC
        # Implementation hier wenn kontinuierliche Actions gewünscht sind
        pass


def create_trading_agent(env,
                        agent_type: str = "ppo",
                        config: Optional[Dict] = None) -> Union[TradingPPOAgent, TradingSACAgent]:
    """
    Factory function für Trading Agents
    """
    config = config or {}

    if agent_type.lower() == "ppo":
        return TradingPPOAgent(env, **config)
    elif agent_type.lower() == "sac":
        return TradingSACAgent(env, **config)
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


# Example usage
if __name__ == "__main__":
    from src.env import InteractiveTradingEnv
    from src.data_feed import create_sample_data

    # Create sample data and environment
    df = create_sample_data(periods=1000)
    env = InteractiveTradingEnv(df, enable_patterns=True)

    # Create agent
    agent = TradingPPOAgent(
        env=env,
        use_wandb=False,
        model_name="test_agent"
    )

    print("Agent created successfully!")
    print("Run agent.train() to start training with human feedback")

    # Example evaluation
    # stats = agent.evaluate(n_episodes=3)
    # print(f"Evaluation stats: {stats}")