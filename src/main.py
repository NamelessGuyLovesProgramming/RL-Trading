"""
Interactive RL Trading System - Main Entry Point
Inspiriert vom Trackmania Human Feedback Beispiel
"""

import argparse
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging
from dotenv import load_dotenv

# Add src to path
sys.path.append(str(Path(__file__).parent))

from env import InteractiveTradingEnv
from agent import TradingPPOAgent, create_trading_agent
from data_feed import TradingDataManager, create_sample_data
from rewards import RewardManager
from patterns import PatternManager


class InteractiveTrainer:
    """
    Main trainer class für Human-in-the-Loop RL Trading
    """

    def __init__(self,
                 symbols: list = ["BTCUSDT"],
                 use_live_data: bool = False,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None):

        self.symbols = symbols
        self.use_live_data = use_live_data
        self.api_key = api_key
        self.api_secret = api_secret

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.data_manager = None
        self.env = None
        self.agent = None

        self.logger.info("Interactive Trainer initialized")

    def setup_data(self, symbol: str = "BTCUSDT", periods: int = 1000) -> pd.DataFrame:
        """Setup data source (live or sample)"""

        if self.use_live_data and self.api_key:
            self.logger.info("Setting up live data feed...")

            try:
                self.data_manager = TradingDataManager(
                    symbols=[symbol],
                    api_key=self.api_key,
                    api_secret=self.api_secret
                )

                # Start data collection
                self.data_manager.start()

                # Wait for initial data
                import time
                time.sleep(5)

                df = self.data_manager.get_current_data(symbol)

                if df.empty:
                    self.logger.warning("No live data received, falling back to sample data")
                    df = create_sample_data(symbol, periods)
                else:
                    self.logger.info(f"Live data loaded: {len(df)} records")

            except Exception as e:
                self.logger.error(f"Live data setup failed: {e}")
                self.logger.info("Falling back to sample data")
                df = create_sample_data(symbol, periods)

        else:
            self.logger.info("Using sample data...")
            df = create_sample_data(symbol, periods)

        self.logger.info(f"Data setup complete: {len(df)} records")
        return df

    def setup_environment(self, df: pd.DataFrame, config: Optional[Dict] = None) -> InteractiveTradingEnv:
        """Setup trading environment"""

        env_config = {
            'initial_cash': 10000,
            'transaction_cost': 0.001,
            'max_position_size': 1.0,
            'enable_patterns': True
        }

        if config:
            env_config.update(config)

        self.env = InteractiveTradingEnv(df, **env_config)
        self.logger.info("Trading environment setup complete")

        return self.env

    def setup_agent(self, agent_config: Optional[Dict] = None) -> TradingPPOAgent:
        """Setup RL agent"""

        default_config = {
            'learning_rate': 3e-4,
            'n_steps': 2048,
            'batch_size': 64,
            'use_wandb': False,
            'model_name': 'interactive_trading_agent'
        }

        if agent_config:
            default_config.update(agent_config)

        self.agent = create_trading_agent(self.env, "ppo", default_config)
        self.logger.info("RL agent setup complete")

        return self.agent

    def run_demo_mode(self, n_episodes: int = 3):
        """
        Demo Mode - Menschliche Demonstration sammeln
        Wie im Trackmania Beispiel wo der Entwickler manually driftet
        """
        print("\n" + "="*60)
        print("[DEMO] Human Demonstrations Mode")
        print("="*60)
        print("Actions: 0=Hold, 1=Buy, 2=Sell")
        print("You'll trade manually and rate your own trades!")
        print("This teaches the AI what good trading looks like.")
        print("="*60)

        demonstrations = []

        for episode in range(n_episodes):
            print(f"\n[*] Episode {episode + 1}/{n_episodes}")
            print("-" * 30)

            obs, _ = self.env.reset()
            episode_data = []
            done = False
            step_count = 0

            while not done and step_count < 100:  # Limit steps for demo
                # Show current state
                current_price = self.env.df.iloc[self.env.current_step]['close']
                portfolio_value = self.env.cash + self.env.shares_held * current_price

                print(f"\nStep {self.env.current_step}")
                print(f"[PRICE] Price: ${current_price:.2f}")
                print(f"[CASH] Cash: ${self.env.cash:.2f}")
                print(f"[INFO] Position: {self.env.shares_held} shares")
                print(f"[PORTFOLIO] Portfolio: ${portfolio_value:.2f}")

                # Get pattern info if available
                if hasattr(self.env, 'pattern_manager'):
                    signals = self.env.pattern_manager.get_trading_signals(
                        self.env.df, self.env.current_step
                    )
                    print(f"[PATTERNS] FVG={signals['in_fvg_zone']}, "
                          f"OB={signals['near_support_ob'] or signals['near_resistance_ob']}")

                # Get human action
                try:
                    action = int(input("Your action (0=Hold, 1=Buy, 2=Sell): "))
                    if action not in [0, 1, 2]:
                        action = 0
                except (ValueError, KeyboardInterrupt):
                    print("\nDemo interrupted by user")
                    return demonstrations

                # Execute action
                next_obs, reward, done, _, info = self.env.step(action)
                episode_data.append((obs, action, reward, next_obs, done, info))

                # Show trade result
                if info['trade_info']['executed']:
                    trade = info['trade_info']
                    print(f"[SUCCESS] Trade executed: {trade['type'].upper()}")
                    print(f"   Price: ${trade['price']:.2f}")
                    if 'pnl' in trade:
                        pnl_color = "[PROFIT]" if trade['pnl'] > 0 else "[LOSS]"
                        print(f"   PnL: {pnl_color} ${trade['pnl']:.2f}")

                    # Rate the trade
                    try:
                        feedback = input("Rate this trade (-1=bad, 0=neutral, 1=good): ")
                        if feedback:
                            feedback_value = float(feedback)
                            feedback_value = max(-1, min(1, feedback_value))
                            self.env.add_human_feedback(feedback_value)
                            print(f"[FEEDBACK] Feedback recorded: {feedback_value}")
                    except ValueError:
                        print("[FEEDBACK] No feedback recorded")

                obs = next_obs
                step_count += 1

            demonstrations.append(episode_data)
            final_value = info['portfolio_value']
            pnl_pct = (final_value / 10000 - 1) * 100
            pnl_color = "[PROFIT]" if pnl_pct > 0 else "[LOSS]"

            print(f"\n[RESULTS] Episode {episode + 1} Results:")
            print(f"   Final Portfolio: ${final_value:.2f}")
            print(f"   PnL: {pnl_color} {pnl_pct:.2f}%")
            print(f"   Trades: {self.env.total_trades}")
            print(f"   Win Rate: {self.env.winning_trades/max(1, self.env.total_trades)*100:.1f}%")

        print(f"\n[SUCCESS] Demo complete! Collected {len(demonstrations)} episodes")
        print("This data will help train the AI to trade like you!")

        return demonstrations

    def run_training_mode(self,
                         total_timesteps: int = 10000,
                         feedback_interval: int = 1000,
                         save_interval: int = 5000):
        """
        Training Mode mit periodischem Human Feedback
        Wie Trackmania wo periodisch Feedback für das Drift-Verhalten gegeben wird
        """
        print("\n" + "="*60)
        print("[AI] TRAINING MODE - Human-in-the-Loop Learning")
        print("="*60)
        print("The AI will trade and ask for your feedback periodically.")
        print("This is like teaching it to 'drift' in trading patterns!")
        print(f"Training for {total_timesteps} timesteps...")
        print("="*60)

        try:
            # Configure human feedback in agent
            if hasattr(self.agent, 'human_feedback_callback'):
                self.agent.human_feedback_callback.feedback_interval = feedback_interval
                self.agent.human_feedback_callback.auto_feedback = False

            # Start training
            self.agent.train(
                total_timesteps=total_timesteps,
                feedback_enabled=True,
                save_interval=save_interval
            )

            print("\n[SUCCESS] Training completed!")

            # Show training stats
            stats = self.agent.get_training_stats()
            if stats:
                print(f"[STATS] Training Statistics:")
                for key, value in stats.items():
                    print(f"   {key}: {value}")

        except KeyboardInterrupt:
            print("\n[STOP] Training interrupted by user")
            self.agent.save_model(suffix="_interrupted")

    def run_evaluation_mode(self, n_episodes: int = 5, model_path: Optional[str] = None):
        """
        Evaluation Mode - Teste den trainierten Agent
        """
        print("\n" + "="*60)
        print("[EVAL] EVALUATION MODE")
        print("="*60)

        if model_path:
            print(f"Loading model from: {model_path}")
            self.agent.load_model(model_path)

        print(f"Evaluating agent over {n_episodes} episodes...")
        print("="*60)

        results = self.agent.evaluate(n_episodes=n_episodes)

        print(f"\n[EVALUATION] Results:")
        print(f"   Average Reward: {results['mean_reward']:.2f} ± {results['std_reward']:.2f}")
        print(f"   Average Episode Length: {results['mean_length']:.0f}")
        print(f"   Average Win Rate: {results['mean_win_rate']:.2%}")
        print(f"   Best Episode: {results['max_reward']:.2f}")
        print(f"   Worst Episode: {results['min_reward']:.2f}")

        return results

    def run_live_mode(self):
        """
        Live Mode - Trading mit echten Daten (Paper Trading)
        """
        print("\n" + "="*60)
        print("[LIVE] LIVE MODE - Paper Trading")
        print("="*60)
        print("WARNING: This will use live market data!")
        print("Make sure your model is well-trained before using this mode.")
        print("="*60)

        if not self.use_live_data:
            print("[ERROR] Live mode requires live data. Please restart with --live flag.")
            return

        confirm = input("Continue with live paper trading? (y/N): ")
        if confirm.lower() != 'y':
            print("Live mode cancelled.")
            return

        print("[LIVE] Starting live paper trading...")

        # Implementation für Live Trading
        # Hier würde eine kontinuierliche Schleife laufen die:
        # 1. Neue Daten von der API holt
        # 2. Agent Predictions macht
        # 3. Trades ausführt (paper)
        # 4. Performance tracked

        print("Live mode would be implemented here...")

    def cleanup(self):
        """Cleanup resources"""
        if self.data_manager:
            self.data_manager.stop()
        self.logger.info("Cleanup completed")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Interactive RL Trading System")

    parser.add_argument("--mode", type=str, default="demo",
                       choices=["demo", "train", "eval", "live"],
                       help="Execution mode")

    parser.add_argument("--symbol", type=str, default="NQ",
                       help="Trading symbol")

    parser.add_argument("--live", action="store_true",
                       help="Use live data (requires API keys)")

    parser.add_argument("--episodes", type=int, default=3,
                       help="Number of episodes for demo/eval")

    parser.add_argument("--timesteps", type=int, default=10000,
                       help="Training timesteps")

    parser.add_argument("--model", type=str, default=None,
                       help="Model path for evaluation")

    parser.add_argument("--config", type=str, default=None,
                       help="Config file path")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Get API keys from environment
    api_key = os.getenv("BINANCE_API_KEY") if args.live else None
    api_secret = os.getenv("BINANCE_API_SECRET") if args.live else None

    # Initialize trainer
    trainer = InteractiveTrainer(
        symbols=[args.symbol],
        use_live_data=args.live,
        api_key=api_key,
        api_secret=api_secret
    )

    try:
        print("[START] Interactive RL Trading System...")
        print(f"Mode: {args.mode.upper()}")
        print(f"Symbol: {args.symbol}")
        print(f"Data: {'LIVE' if args.live else 'SAMPLE'}")

        # Setup data and environment
        df = trainer.setup_data(args.symbol, periods=1000)
        env = trainer.setup_environment(df)

        if args.mode in ["train", "eval"]:
            # Setup agent for training/evaluation
            agent = trainer.setup_agent()

        # Run selected mode
        if args.mode == "demo":
            trainer.run_demo_mode(n_episodes=args.episodes)

        elif args.mode == "train":
            trainer.run_training_mode(total_timesteps=args.timesteps)

        elif args.mode == "eval":
            trainer.run_evaluation_mode(n_episodes=args.episodes, model_path=args.model)

        elif args.mode == "live":
            trainer.run_live_mode()

        print("\n[COMPLETE] Session completed successfully!")

    except KeyboardInterrupt:
        print("\n[STOP] Session interrupted by user")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        trainer.cleanup()


if __name__ == "__main__":
    main()