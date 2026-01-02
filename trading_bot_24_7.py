"""
24/7 Institutional Trading Bot for Binance
BTC/USDC & ETH/USDC Automated Trading
Features:
- Auto-restart on errors
- Risk management
- Position sizing
- Real-time monitoring
- Email alerts (optional)
"""

import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", module="sklearn")
warnings.filterwarnings("ignore", module="dask")

import ccxt
import pandas as pd
import numpy as np
import pickle
import json
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import glob
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys
import traceback
import sqlite3
import csv
from utils.indicators import calculate_institutional_composite


# First-time setup function
def first_time_setup():
    """Interactive setup for first-time users"""
    print("\n" + "=" * 60)
    print("🚀 WELCOME TO AI TRADING BOT - FIRST TIME SETUP")
    print("=" * 60)

    # Check if user wants to use existing config
    if os.path.exists("api_config.txt.example"):
        print("\n💡 TIP: You can copy api_config.txt.example and edit manually")
        use_wizard = input("Use setup wizard? (yes/no, default yes): ").strip().lower()
        if use_wizard == "no":
            print(
                "\n📝 Please copy api_config.txt.example to api_config.txt and edit it"
            )
            print("   Command: cp api_config.txt.example api_config.txt")
            sys.exit(0)

    print("\n📝 Step 1: Binance API Configuration")
    print("-" * 60)
    api_key = input("Enter your Binance API Key: ").strip()
    api_secret = input("Enter your Binance API Secret: ").strip()

    print("\n💰 Step 2: Risk Management")
    print("-" * 60)
    print("How much % of your portfolio do you want to risk per trade?")
    print("Example: 2% means if you have $1000, each trade = $20")
    risk_pct = float(
        input("Risk per trade (% of portfolio, 1-5 recommended): ").strip()
    )

    # Calculate position size from risk
    print(f"\n✓ Risk per trade set to: {risk_pct}%")

    print("\n⚙️ Step 3: Trading Configuration")
    print("-" * 60)
    print("Minimum confidence to execute trade (recommended 65%)")
    print("Format: Enter 40 for 40%, 65 for 65%, 70 for 70%")
    min_conf = input("Minimum confidence % (default 65): ").strip() or "65"
    max_pos = input("Max concurrent positions (default 2): ").strip() or "2"

    print("\n📊 Step 4: Trading Symbols")
    print("-" * 60)
    symbols = (
        input("Symbols to trade (default: BTC/USDC,ETH/USDC): ").strip()
        or "BTC/USDC,ETH/USDC"
    )

    # Create api_config.txt with full path to ensure it's saved in correct location
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "api_config.txt"
    )
    config_content = f"""# Binance API Configuration
BINANCE_API_KEY={api_key}
BINANCE_API_SECRET={api_secret}

# Risk Management
RISK_PER_TRADE_PCT={risk_pct}

# Trading Configuration
MIN_CONFIDENCE={float(min_conf)/100}
MAX_POSITIONS={max_pos}
STOP_LOSS_PCT=0.02
TAKE_PROFIT_PCT=0.04
CHECK_INTERVAL=300

# Symbols (comma-separated, no spaces)
SYMBOLS={symbols}
"""

    with open(config_path, "w") as f:
        f.write(config_content)

    print("\n" + "=" * 60)
    print("✅ SETUP COMPLETE!")
    print("=" * 60)
    print(f"\n📁 Configuration saved to: {config_path}")
    print("🔒 This file is gitignored for your security")
    print("\n💡 Next time you run the bot, it will use this config automatically")
    print("   To reconfigure, delete api_config.txt and run again")
    print("\n🚀 Starting bot now...\n")
    time.sleep(3)


# Check if this is first time setup (use absolute path)
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_config.txt")
if not os.path.exists(config_file):
    first_time_setup()
else:
    print("✅ Found existing config: api_config.txt")
    print("💡 To reconfigure, delete api_config.txt and run again\n")

# Import configuration
try:
    from config_loader import *
except ImportError:
    from config import *


# Setup logging with AUTO-ROTATION (7 days, keep 14 days backup)
def setup_logging_with_rotation():
    """Setup logging dengan auto-rotation 7 hari"""
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(log_dir, LOG_FILE)

    # Create rotating file handler (rotate setiap 7 hari, keep 2 backup)
    handler = TimedRotatingFileHandler(
        log_file,
        when="D",  # Daily
        interval=7,  # Every 7 days
        backupCount=2,  # Keep 2 old log files (2 weeks backup)
        encoding="utf-8",
    )
    handler.suffix = "%Y%m%d"  # Suffix: trading_bot_24_7.log.20251229

    # Format log messages
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # Setup logger
    logger_root = logging.getLogger()
    logger_root.setLevel(getattr(logging, LOG_LEVEL))
    logger_root.addHandler(handler)

    # Also print to console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger_root.addHandler(console_handler)

    # Cleanup old log files manually (older than 14 days)
    cleanup_old_logs(log_dir)

    return logger_root


def cleanup_old_logs(log_dir, days=14):
    """Delete log files older than X days"""
    import time

    log_pattern = os.path.join(log_dir, "trading_bot_24_7.log.*")
    current_time = time.time()
    days_in_seconds = days * 86400

    for log_file in glob.glob(log_pattern):
        file_age = current_time - os.path.getmtime(log_file)
        if file_age > days_in_seconds:
            try:
                os.remove(log_file)
                print(f"[CLEANUP] Deleted old log: {os.path.basename(log_file)}")
            except Exception as e:
                print(f"[ERROR] Could not delete {log_file}: {e}")


# Initialize logging
setup_logging_with_rotation()

# Force UTF-8 for stdout
if sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)


class InstitutionalTradingBot:
    """24/7 automated trading bot"""

    def __init__(self, leverage=1, risk_per_trade_pct=None):
        """Initialize bot"""
        logger.info("=" * 80)
        logger.info(" [INSTITUTIONAL BOT] - 24/7 Automated Trading System")
        logger.info("=" * 80)

        # Store risk per trade (override config if provided) - SET EARLY!
        if risk_per_trade_pct is not None:
            self.risk_per_trade_pct = risk_per_trade_pct
        else:
            try:
                self.risk_per_trade_pct = RISK_PER_TRADE_PCT
            except NameError:
                self.risk_per_trade_pct = 2.0  # Default fallback

        # Initialize exchange
        self.exchange = ccxt.binance(
            {
                "apiKey": API_KEY,
                "secret": API_SECRET,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "future" if leverage > 1 else "spot",
                    "adjustForTimeDifference": True,  # Auto-sync dengan server time
                    "recvWindow": 60000,  # 60 detik tolerance untuk timestamp
                },
            }
        )

        # Load server time untuk sync
        try:
            self.exchange.load_time_difference()
            logger.info("[SYNC] Time synchronized with Binance server")
        except:
            pass

        # Set leverage
        self.leverage = leverage
        if leverage > 1:
            for symbol in SYMBOLS:
                try:
                    self.exchange.set_leverage(leverage, symbol)
                    logger.info(f"[LEVERAGE] Set {leverage}x for {symbol}")
                except:
                    pass

        # Load latest model
        self.load_model()

        # Track positions
        self.positions = {}
        self.executed_signals = set()

        # ANTI-SPAM PROTECTION: Track recent trades and failures
        self.recent_trades = {}  # {symbol: last_trade_timestamp}
        self.trade_cooldown = 300  # 5 minutes cooldown between same symbol trades
        self.failed_attempts = {}  # {symbol: failed_count}
        self.max_failed_attempts = 3  # Max failed attempts before longer cooldown
        logger.info("[ANTI-SPAM] Trade cooldown: 5 minutes per symbol")
        logger.info("[ANTI-SPAM] Max failed attempts: 3 before extended cooldown")

        # Initialize trade history tracking
        self.trade_history = []
        self.win_streak = 0
        self.loss_streak = 0

        # Live P&L tracking
        self.total_pnl = 0.0
        self.daily_pnl = 0.0
        self.session_start_balance = 0.0
        self.initial_balance = 0.0
        self.today_date = datetime.now().date()

        # Initialize database
        self.db_conn = sqlite3.connect("trades.db")
        self.init_database()

        # Track model training date
        self.last_train_date = datetime.now()
        self.model_backups = []

        # Show balance
        self.show_balance()

        logger.info(f"\n[CONFIG]")
        logger.info(f"  Symbols: {', '.join(SYMBOLS)}")
        logger.info(f"  Risk per Trade: {self.risk_per_trade_pct}% of portfolio")
        logger.info(f"  Leverage: {leverage}x")
        logger.info(f"  Max Positions: {MAX_POSITIONS}")
        logger.info(f"  Stop Loss: {STOP_LOSS_PCT*100}%")
        logger.info(f"  Take Profit: {TAKE_PROFIT_PCT*100}%")
        logger.info(f"  Min Confidence: {MIN_CONFIDENCE*100:.0f}% (Prioritas: 65%+)")
        logger.info(f"  Check Interval: {CHECK_INTERVAL}s\n")

    def load_model(self):
        """Load latest model (ensemble or single)"""
        try:
            # Check for ENSEMBLE models first (preferred)
            ensemble_metadata_files = list(
                Path("models").glob("ensemble_metadata_*.json")
            )

            if ensemble_metadata_files:
                # Load ENSEMBLE MODELS (HYBRID SYSTEM)
                latest_metadata = max(
                    ensemble_metadata_files, key=lambda x: x.stat().st_mtime
                )

                with open(latest_metadata, "r") as f:
                    metadata = json.load(f)

                logger.info(f"[ENSEMBLE MODEL] Loading hybrid dual-model system...")

                # Load long-term model
                with open(metadata["long_term"]["model_path"], "rb") as f:
                    long_data = pickle.load(f)

                # Load short-term model
                with open(metadata["short_term"]["model_path"], "rb") as f:
                    short_data = pickle.load(f)

                # Store ensemble components
                self.model_long = long_data["model"]
                self.scaler_long = long_data["scaler"]
                self.selector_long = long_data["selector"]
                self.features_long = long_data["features"]

                self.model_short = short_data["model"]
                self.scaler_short = short_data["scaler"]
                self.selector_short = short_data["selector"]
                self.features_short = short_data["features"]

                # Weights for ensemble
                self.weight_long = metadata["long_term"]["weight"]
                self.weight_short = metadata["short_term"]["weight"]

                # Use ensemble mode
                self.use_ensemble = True
                self.feature_cols = list(set(self.features_long + self.features_short))

                logger.info(
                    f"  ✅ Long-term (6M): {metadata['long_term']['accuracy']*100:.2f}% acc, weight={self.weight_long}"
                )
                logger.info(
                    f"  ✅ Short-term (30D): {metadata['short_term']['accuracy']*100:.2f}% acc, weight={self.weight_short}"
                )
                logger.info(
                    f"  🎯 Ensemble: {metadata['ensemble']['weighted_accuracy']*100:.2f}% weighted accuracy"
                )

            else:
                # Fallback to SINGLE MODEL
                model_files = list(
                    Path("models").glob("institutional_model_usdc_*.pkl")
                )
                if not model_files:
                    raise FileNotFoundError(
                        "No model found! Run train_hybrid_ensemble.py or train_institutional.py first"
                    )

                latest_model = max(model_files, key=lambda x: x.stat().st_mtime)

                with open(latest_model, "rb") as f:
                    model_data = pickle.load(f)

                self.model = model_data["model"]
                self.scaler = model_data["scaler"]
                self.feature_cols = model_data["feature_cols"]
                self.use_ensemble = False

                logger.info(f"[SINGLE MODEL] Loaded: {latest_model.name}")
                logger.info(f"  Test Accuracy: {model_data['test_acc']*100:.2f}%")
                logger.info(f"  ROC-AUC: {model_data['roc_auc']:.4f}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to load model: {e}")
            sys.exit(1)

    def show_balance(self):
        """Show account balance with live P&L"""
        try:
            balance = self.exchange.fetch_balance()
            
            # DEBUG: Log what we receive from exchange
            logger.debug(f"[DEBUG] Balance response keys: {list(balance.keys())}")
            if 'total' in balance:
                logger.debug(f"[DEBUG] Available assets in total: {list(balance['total'].keys())}")
            
            total_usdc = balance["total"].get("USDC", 0)
            free_usdc = balance["free"].get("USDC", 0)

            # Safety check for zero balance
            if total_usdc <= 0:
                logger.warning(f"[WARNING] No USDC balance found or balance is zero")
                logger.info(
                    f"[BALANCE] Total: ${total_usdc:.2f}, Free: ${free_usdc:.2f}"
                )
                return

            # Set initial balance on first call
            if self.initial_balance == 0.0:
                self.initial_balance = total_usdc
                self.session_start_balance = total_usdc

            # Calculate dynamic position size based on risk %
            risk_pct = self.risk_per_trade_pct
            risk_amount = total_usdc * (risk_pct / 100)  # Amount at risk

            # Position size calculation:
            # If we risk X% of portfolio with Y% stop loss, position size = (Portfolio * X%) / Y%
            # Example: $100 portfolio, 5% risk ($5), 2% SL → Position = $5 / 0.02 = $250
            # If SL hit: $250 * 2% = $5 loss (exactly our risk amount!)
            calculated_position_size = risk_amount / STOP_LOSS_PCT
            self.current_position_size = calculated_position_size

            # Margin required (for leveraged trading)
            margin_required = (
                calculated_position_size / self.leverage
                if self.leverage > 1
                else calculated_position_size
            )

            # SAFETY CHECK: Validate margin doesn't exceed portfolio
            margin_pct = (margin_required / total_usdc) * 100
            if margin_pct > 95:
                logger.error(
                    f"\n⚠️ [MARGIN ERROR] Margin required ${margin_required:,.2f} ({margin_pct:.1f}%) exceeds portfolio ${total_usdc:,.2f}!"
                )
                logger.error(f"   This will cause 'Insufficient Margin' error!")
                logger.error(f"   Solutions:")
                logger.error(f"   1. Increase leverage (current: {self.leverage}x)")
                logger.error(f"   2. Reduce risk per trade (current: {risk_pct}%)")
                logger.error(f"   3. Add more capital")
                # Adjust position size to use max 90% of portfolio
                max_margin = total_usdc * 0.90
                calculated_position_size = max_margin * self.leverage
                margin_required = max_margin
                logger.warning(
                    f"   Auto-adjusted position to ${calculated_position_size:,.2f} (margin: ${margin_required:,.2f}, {margin_required/total_usdc*100:.1f}%)"
                )

            # Calculate ROI
            if self.initial_balance > 0:
                roi_pct = (
                    (total_usdc - self.initial_balance) / self.initial_balance
                ) * 100
            else:
                roi_pct = 0.0

            logger.info(f"\n[BALANCE]")
            logger.info(
                f"  Portfolio: ${total_usdc:,.2f} (Initial: ${self.initial_balance:.2f})"
            )
            logger.info(
                f"  Free: ${free_usdc:,.2f} ({free_usdc/total_usdc*100:.1f}% available)"
            )

            logger.info(f"\n[PORTFOLIO PERFORMANCE]")
            logger.info(
                f"  📈 Total P&L: ${total_usdc - self.initial_balance:+,.2f} ({roi_pct:+.2f}%)"
            )
            logger.info(
                f"  💵 Session P&L: ${total_usdc - self.session_start_balance:+,.2f}"
            )

            # Get trade statistics from database
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            total_trades = cursor.fetchone()[0]

            if total_trades > 0:
                cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0")
                wins = cursor.fetchone()[0]
                win_rate = (wins / total_trades) * 100

                cursor.execute(
                    "SELECT MAX(pnl), MIN(pnl), AVG(CASE WHEN pnl > 0 THEN pnl END), AVG(CASE WHEN pnl < 0 THEN pnl END) FROM trades"
                )
                best, worst, avg_win, avg_loss = cursor.fetchone()

                logger.info(f"  🎯 Total Trades: {total_trades}")
                logger.info(
                    f"  ✅ Win Rate: {win_rate:.1f}% ({wins}W/{total_trades-wins}L)"
                )
                if best:
                    logger.info(f"  💰 Best Trade: ${best:+.2f}")
                if worst:
                    logger.info(f"  📉 Worst Trade: ${worst:+.2f}")
                if avg_win:
                    logger.info(f"  📈 Avg Win: ${avg_win:+.2f}")
                if avg_loss:
                    logger.info(f"  📉 Avg Loss: ${avg_loss:+.2f}")

            logger.info(f"\n[RISK MANAGEMENT]")
            logger.info(f"  Risk per Trade: {risk_pct}% → ${risk_amount:,.2f} max loss")
            logger.info(f"  Position Size: ${calculated_position_size:,.2f} (exposure)")
            logger.info(
                f"  Margin Required: ${margin_required:,.2f} ({margin_required/total_usdc*100:.1f}% of portfolio)"
            )
            logger.info(
                f"  Stop Loss: {STOP_LOSS_PCT*100}% → ${calculated_position_size * STOP_LOSS_PCT:,.2f} loss if hit"
            )

            if self.leverage > 1:
                logger.info(f"  Leverage: {self.leverage}x")
                logger.info(
                    f"  Max Buying Power: ${total_usdc * self.leverage:,.2f} (all-in)"
                )
        except Exception as e:
            logger.warning(f"[WARNING] Could not fetch balance: {e}")

    def init_database(self):
        """Initialize SQLite database for trade history"""
        cursor = self.db_conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                action TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity REAL,
                confidence REAL,
                stop_loss REAL,
                take_profit REAL,
                exit_reason TEXT,
                pnl REAL,
                pnl_pct REAL,
                leverage INTEGER,
                duration_seconds INTEGER
            )
        """
        )
        self.db_conn.commit()
        logger.info("[DATABASE] Trade history database initialized")

    def save_trade(self, trade_data):
        """Save trade to database"""
        cursor = self.db_conn.cursor()
        cursor.execute(
            """
            INSERT INTO trades (timestamp, symbol, action, entry_price, exit_price, 
                              quantity, confidence, stop_loss, take_profit, exit_reason,
                              pnl, pnl_pct, leverage, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                trade_data["timestamp"],
                trade_data["symbol"],
                trade_data["action"],
                trade_data["entry_price"],
                trade_data["exit_price"],
                trade_data["quantity"],
                trade_data["confidence"],
                trade_data["stop_loss"],
                trade_data["take_profit"],
                trade_data["exit_reason"],
                trade_data["pnl"],
                trade_data["pnl_pct"],
                trade_data["leverage"],
                trade_data["duration"],
            ),
        )
        self.db_conn.commit()

    def get_analytics(self):
        """Get trading analytics"""
        cursor = self.db_conn.cursor()

        # Win rate
        cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0")
        wins = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM trades")
        total = cursor.fetchone()[0]
        win_rate = (wins / total * 100) if total > 0 else 0

        # Average profit/loss
        cursor.execute("SELECT AVG(pnl) FROM trades WHERE pnl > 0")
        avg_win = cursor.fetchone()[0] or 0
        cursor.execute("SELECT AVG(pnl) FROM trades WHERE pnl < 0")
        avg_loss = cursor.fetchone()[0] or 0

        # Best pair
        cursor.execute(
            "SELECT symbol, AVG(pnl) as avg_pnl FROM trades GROUP BY symbol ORDER BY avg_pnl DESC LIMIT 1"
        )
        best_pair = cursor.fetchone()

        return {
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": abs(avg_loss) if avg_loss else 0,
            "best_pair": best_pair[0] if best_pair else None,
            "best_pair_avg": best_pair[1] if best_pair else 0,
        }

    def export_to_csv(self, filename="trade_history.csv"):
        """Export trades to CSV for tax reporting"""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM trades")
        trades = cursor.fetchall()

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "ID",
                    "Timestamp",
                    "Symbol",
                    "Action",
                    "Entry Price",
                    "Exit Price",
                    "Quantity",
                    "Confidence",
                    "Stop Loss",
                    "Take Profit",
                    "Exit Reason",
                    "P&L",
                    "P&L %",
                    "Leverage",
                    "Duration",
                ]
            )
            writer.writerows(trades)

        logger.info(f"[EXPORT] Trade history exported to {filename}")

    def should_retrain(self):
        """Check if 7 days passed since last training"""
        days_since = (datetime.now() - self.last_train_date).days
        return days_since >= 7

    def backup_model(self):
        """Backup current model before retraining"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path("models/backup")
        backup_dir.mkdir(exist_ok=True, parents=True)
        backup_path = backup_dir / f"institutional_model_usdc_{timestamp}.pkl"

        # Save current model
        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_cols": self.feature_cols,
            "backup_date": timestamp,
        }

        with open(backup_path, "wb") as f:
            pickle.dump(model_data, f)

        self.model_backups.append(str(backup_path))

        # Keep only last 5 backups
        if len(self.model_backups) > 5:
            old_backup = self.model_backups.pop(0)
            try:
                Path(old_backup).unlink()
                logger.info(f"[BACKUP] Removed old backup: {old_backup}")
            except:
                pass

        logger.info(f"[BACKUP] Model backed up to {backup_path}")
        return str(backup_path)

    def retrain_model(self):
        """Retrain model with latest data"""
        logger.info("\n[RETRAIN] Starting model retraining...")

        # Backup current model
        backup_path = self.backup_model()

        # Run training script
        import subprocess

        result = subprocess.run(
            ["python", "train_institutional.py"], capture_output=True, text=True
        )

        if result.returncode == 0:
            logger.info("[RETRAIN] Training completed successfully")
            logger.info(f"[RETRAIN] Reloading new model...")

            # Reload new model
            try:
                self.load_model()
                self.last_train_date = datetime.now()
                logger.info(f"[RETRAIN] New model loaded successfully")
                logger.info(
                    f"[RETRAIN] Next retrain scheduled for {(self.last_train_date + timedelta(days=7)).strftime('%Y-%m-%d')}"
                )
            except Exception as e:
                logger.error(f"[RETRAIN] Failed to load new model: {e}")
                logger.warning(f"[RETRAIN] Restoring backup: {backup_path}")
                # Restore backup if new model fails
                with open(backup_path, "rb") as f:
                    backup_data = pickle.load(f)
                    self.model = backup_data["model"]
                    self.scaler = backup_data["scaler"]
                    self.feature_cols = backup_data["feature_cols"]
        else:
            logger.error(f"[RETRAIN] Training failed: {result.stderr}")
            logger.warning(f"[RETRAIN] Continuing with current model")

    def calculate_kelly_size(self, win_rate, avg_win, avg_loss):
        """Kelly Criterion: f = (p*b - q) / b"""
        # Use dynamic position size
        base_size = (
            self.current_position_size
            if hasattr(self, "current_position_size")
            else POSITION_SIZE_USD
        )

        if win_rate == 0 or avg_win == 0 or avg_loss == 0:
            return base_size

        p = win_rate  # Probability of win
        q = 1 - p  # Probability of loss
        b = avg_win / avg_loss if avg_loss > 0 else 1

        kelly_fraction = (p * b - q) / b
        kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25%

        return base_size * (1 + kelly_fraction)

    def adjust_position_size(self):
        """Adjust size based on recent performance"""
        # Use dynamic position size
        base_size = (
            self.current_position_size
            if hasattr(self, "current_position_size")
            else POSITION_SIZE_USD
        )

        if len(self.trade_history) < 10:
            return base_size

        recent = self.trade_history[-20:]
        wins = [t for t in recent if t["pnl"] > 0]
        losses = [t for t in recent if t["pnl"] < 0]

        if not recent:
            return base_size

        win_rate = len(wins) / len(recent)
        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
        avg_loss = abs(np.mean([t["pnl"] for t in losses])) if losses else 0

        kelly_size = self.calculate_kelly_size(win_rate, avg_win, avg_loss)

        # Adjust for streaks
        if self.win_streak >= 3:
            kelly_size *= 1.2  # Increase 20% after 3 wins
            logger.info(f"[KELLY] Win streak bonus: +20%")
        elif self.loss_streak >= 2:
            kelly_size *= 0.5  # Reduce 50% after 2 losses
            logger.info(f"[KELLY] Loss streak protection: -50%")

        # Cap between 50% and 200% of base size
        final_size = max(base_size * 0.5, min(kelly_size, base_size * 2))

        logger.info(
            f"[KELLY] Position size: ${final_size:.2f} (Base: ${base_size:.2f}, Win rate: {win_rate*100:.1f}%)"
        )

        return final_size

    def check_multi_timeframe_alignment(self, symbol):
        """Check trend alignment across 1H and 4H"""
        try:
            # Fetch 4H data
            ohlcv_4h = self.exchange.fetch_ohlcv(symbol, "4h", limit=200)
            df_4h = pd.DataFrame(
                ohlcv_4h,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )

            # Calculate EMAs for 4H
            ema_50_4h = df_4h["close"].ewm(span=50).mean().iloc[-1]
            ema_200_4h = df_4h["close"].ewm(span=200).mean().iloc[-1]
            current_price_4h = df_4h["close"].iloc[-1]

            # Determine 4H trend
            if current_price_4h > ema_50_4h > ema_200_4h:
                trend_4h = "BULLISH"
            elif current_price_4h < ema_50_4h < ema_200_4h:
                trend_4h = "BEARISH"
            else:
                trend_4h = "NEUTRAL"

            # Get 1H trend from existing data
            df_1h = self.fetch_latest_data(symbol)
            if df_1h is None or len(df_1h) < 200:
                return {
                    "aligned": False,
                    "trend_1h": "UNKNOWN",
                    "trend_4h": trend_4h,
                    "strength": "WEAK",
                }

            df_1h = self.add_features(df_1h)
            ema_50_1h = df_1h["ema_55"].iloc[-1]
            ema_200_1h = df_1h["ema_200"].iloc[-1]
            current_price_1h = df_1h["close"].iloc[-1]

            # Determine 1H trend
            if current_price_1h > ema_50_1h > ema_200_1h:
                trend_1h = "BULLISH"
            elif current_price_1h < ema_50_1h < ema_200_1h:
                trend_1h = "BEARISH"
            else:
                trend_1h = "NEUTRAL"

            # Check alignment
            aligned = trend_1h == trend_4h == "BULLISH"
            strength = "STRONG" if aligned else "WEAK"

            return {
                "aligned": aligned,
                "trend_1h": trend_1h,
                "trend_4h": trend_4h,
                "strength": strength,
            }

        except Exception as e:
            logger.error(f"[ERROR] MTF check failed: {e}")
            return {
                "aligned": False,
                "trend_1h": "ERROR",
                "trend_4h": "ERROR",
                "strength": "WEAK",
            }

    def fetch_latest_data(self, symbol, limit=200):
        """Fetch latest market data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
        except Exception as e:
            logger.error(f"[ERROR] Failed to fetch {symbol}: {e}")
            return None

    def add_features(self, df):
        """Add all features - MUST MATCH TRAINING EXACTLY!"""
        # Basic price features
        df["returns"] = df["close"].pct_change()
        df["log_returns"] = np.log(df["close"] / df["close"].shift(1))

        # === TREND INDICATORS ===
        for period in [8, 21, 55, 89, 200]:
            df[f"ema_{period}"] = df["close"].ewm(span=period).mean()
            df[f"ema_{period}_slope"] = df[f"ema_{period}"].pct_change(5)

        # MACD
        df["ema_12"] = df["close"].ewm(span=12).mean()
        df["ema_26"] = df["close"].ewm(span=26).mean()
        df["macd"] = df["ema_12"] - df["ema_26"]
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]
        df["macd_histogram_slope"] = df["macd_histogram"].pct_change(3)

        # === MOMENTUM INDICATORS ===
        # RSI
        for period in [14, 21]:
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

        # Stochastic RSI
        rsi = df["rsi_14"]
        stoch_rsi = (rsi - rsi.rolling(window=14).min()) / (
            rsi.rolling(window=14).max() - rsi.rolling(window=14).min()
        )
        df["stoch_rsi"] = stoch_rsi * 100

        # ROC
        for period in [9, 21]:
            df[f"roc_{period}"] = (
                (df["close"] - df["close"].shift(period)) / df["close"].shift(period)
            ) * 100

        # === VOLATILITY INDICATORS ===
        # ATR
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1)),
            ),
        )
        df["atr_14"] = df["tr"].rolling(window=14).mean()
        df["atr_pct"] = (df["atr_14"] / df["close"]) * 100

        # Bollinger Bands
        for period in [20, 50]:
            sma = df["close"].rolling(window=period).mean()
            std = df["close"].rolling(window=period).std()
            df[f"bb_upper_{period}"] = sma + (std * 2)
            df[f"bb_lower_{period}"] = sma - (std * 2)
            df[f"bb_width_{period}"] = (
                df[f"bb_upper_{period}"] - df[f"bb_lower_{period}"]
            ) / sma
            df[f"bb_position_{period}"] = (df["close"] - df[f"bb_lower_{period}"]) / (
                df[f"bb_upper_{period}"] - df[f"bb_lower_{period}"]
            )

        # Keltner Channels
        df["kc_middle"] = df["close"].ewm(span=20).mean()
        df["kc_upper"] = df["kc_middle"] + (df["atr_14"] * 2)
        df["kc_lower"] = df["kc_middle"] - (df["atr_14"] * 2)

        # === VOLUME INDICATORS ===
        df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

        # On-Balance Volume
        df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
        df["obv_ema"] = df["obv"].ewm(span=20).mean()

        # VWAP
        df["vwap"] = (
            df["volume"] * (df["high"] + df["low"] + df["close"]) / 3
        ).cumsum() / df["volume"].cumsum()
        df["vwap_distance"] = (df["close"] - df["vwap"]) / df["vwap"] * 100

        # MFI (Money Flow Index)
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        raw_money_flow = typical_price * df["volume"]
        positive_flow = (
            raw_money_flow.where(typical_price > typical_price.shift(1), 0)
            .rolling(14)
            .sum()
        )
        negative_flow = (
            raw_money_flow.where(typical_price < typical_price.shift(1), 0)
            .rolling(14)
            .sum()
        )
        mfi_ratio = positive_flow / negative_flow
        df["mfi"] = 100 - (100 / (1 + mfi_ratio))

        # ADL (Accumulation/Distribution Line)
        clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (
            df["high"] - df["low"]
        )
        df["adl"] = (clv * df["volume"]).fillna(0).cumsum()
        df["adl_ema"] = df["adl"].ewm(span=20).mean()

        # Market Structure
        df["hh"] = (df["high"] > df["high"].shift(1)).astype(int)
        df["ll"] = (df["low"] < df["low"].shift(1)).astype(int)
        df["market_structure"] = df["hh"] - df["ll"]

        # Pivot Points
        df["pivot"] = (
            df["high"].shift(1) + df["low"].shift(1) + df["close"].shift(1)
        ) / 3
        df["r1"] = 2 * df["pivot"] - df["low"].shift(1)
        df["s1"] = 2 * df["pivot"] - df["high"].shift(1)

        # Volatility Regime
        atr_pct_quantiles = df["atr_pct"].quantile([0.33, 0.67])
        try:
            df["vol_regime_numeric"] = pd.cut(
                df["atr_pct"],
                bins=[
                    -np.inf,
                    atr_pct_quantiles.iloc[0],
                    atr_pct_quantiles.iloc[1],
                    np.inf,
                ],
                labels=[0, 1, 2],
                duplicates="drop",
            )
            df["vol_regime_numeric"] = df["vol_regime_numeric"].fillna(1).astype(int)
        except ValueError:
            # If bins are duplicate (constant data), use default value
            df["vol_regime_numeric"] = 1

        # ADX (Average Directional Index) - ONLY adx, not intermediate values
        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        tr_14 = df["tr"].rolling(14).sum()
        plus_di = 100 * (plus_dm.rolling(14).sum() / tr_14)
        minus_di = 100 * (minus_dm.rolling(14).sum() / tr_14)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df["adx"] = dx.rolling(14).mean()  # Only keep adx, not intermediate values

        # === INSTITUTIONAL INDICATORS ===
        df = calculate_institutional_composite(df)

        # === TIME-BASED FEATURES ===
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_asian_session"] = ((df["hour"] >= 0) & (df["hour"] < 8)).astype(int)
        df["is_london_session"] = ((df["hour"] >= 8) & (df["hour"] < 16)).astype(int)
        df["is_ny_session"] = ((df["hour"] >= 13) & (df["hour"] < 21)).astype(int)

        return df

    def generate_signal(self, symbol):
        """Generate trading signal - returns ALL signals with status"""
        try:
            df = self.fetch_latest_data(symbol)
            if df is None or len(df) < 200:
                return None

            df = self.add_features(df)
            df = df.replace([np.inf, -np.inf], np.nan).dropna()

            if len(df) == 0:
                return None

            # Get latest data point
            latest = df.iloc[-1:]

            # Extract features
            exclude_cols = [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "returns",
                "log_returns",
                "target",
                "signal",
            ]
            all_feature_cols = [c for c in df.columns if c not in exclude_cols]
            X = latest[all_feature_cols]

            # ENSEMBLE PREDICTION (if using dual-model system)
            if hasattr(self, "use_ensemble") and self.use_ensemble:
                # Long-term model prediction
                # Use all available features, selector will pick the right ones
                X_long_selected = self.selector_long.transform(X.values.reshape(1, -1))
                X_long_scaled = self.scaler_long.transform(X_long_selected)
                pred_long_proba = self.model_long.predict_proba(X_long_scaled)[0]

                # Short-term model prediction
                X_short_selected = self.selector_short.transform(
                    X.values.reshape(1, -1)
                )
                X_short_scaled = self.scaler_short.transform(X_short_selected)
                pred_short_proba = self.model_short.predict_proba(X_short_scaled)[0]

                # Weighted ensemble (70% long + 30% short)
                proba_all = (pred_long_proba * self.weight_long) + (
                    pred_short_proba * self.weight_short
                )
                prediction = 1 if proba_all[1] > proba_all[0] else 0
                confidence = proba_all.max()

            else:
                # SINGLE MODEL prediction (fallback)
                X_scaled = self.scaler.transform(X)
                prediction = self.model.predict(X_scaled)[0]
                confidence = self.model.predict_proba(X_scaled)[0].max()
                proba_all = self.model.predict_proba(X_scaled)[0]

            current_price = latest["close"].values[0]
            atr = latest["atr_14"].values[0]

            # HYBRID SCALP/SWING MODE
            # >80% confidence = SCALP (1.5% TP, 0.75% SL, quick in/out)
            # 70-80% confidence = SWING (4% TP, 2% SL, hold longer)
            # <70% confidence = SKIP (below threshold)

            if confidence >= 0.80:  # 🔥 SCALP MODE (HIGH CONFIDENCE)
                status = "🔥 SCALP"
                action_type = "LONG" if prediction == 1 else "SHORT"
                reason = f"Scalp mode ({confidence*100:.1f}%) {action_type}"
                executable = True
                trade_mode = "SCALP"
                # Aggressive TP/SL for scalping
                tp_pct = 0.015  # 1.5% TP
                sl_pct = 0.0075  # 0.75% SL

            elif confidence >= MIN_CONFIDENCE:  # ⭐ SWING MODE (MEDIUM-HIGH CONFIDENCE)
                status = "⭐ SWING"
                action_type = "LONG" if prediction == 1 else "SHORT"
                reason = f"Swing mode ({confidence*100:.1f}%) {action_type}"
                executable = True
                trade_mode = "SWING"
                # Standard TP/SL for swing
                tp_pct = TAKE_PROFIT_PCT  # 4% TP
                sl_pct = STOP_LOSS_PCT  # 2% SL

            else:  # ⏸️ SKIP (LOW CONFIDENCE)
                status = "⏸️ SKIP"
                reason = f"Low confidence ({confidence*100:.1f}% < {MIN_CONFIDENCE*100:.0f}%)"
                executable = False
                trade_mode = "NONE"
                tp_pct = TAKE_PROFIT_PCT
                sl_pct = STOP_LOSS_PCT

            # Check multi-timeframe alignment for executable signals (only for LONG)
            mtf = {
                "aligned": True,
                "trend_1h": "N/A",
                "trend_4h": "N/A",
                "strength": "N/A",
            }
            if executable and prediction == 1:  # Only check MTF for LONG positions
                mtf = self.check_multi_timeframe_alignment(symbol)
                if not mtf["aligned"]:
                    status = "⏸️ SKIP"
                    reason = f"MTF not aligned (1H: {mtf['trend_1h']}, 4H: {mtf['trend_4h']})"
                    executable = False

            # Return complete signal data with HYBRID mode
            return {
                "symbol": symbol,
                "action": "BUY" if prediction == 1 else "SELL",
                "side": "LONG" if prediction == 1 else "SHORT",
                "price": current_price,
                "confidence": confidence,
                "proba_buy": proba_all[1],
                "proba_sell": proba_all[0],
                "status": status,
                "reason": reason,
                "executable": executable,
                "trade_mode": trade_mode,  # NEW: SCALP or SWING
                "stop_loss": (
                    current_price * (1 - sl_pct)
                    if prediction == 1
                    else current_price * (1 + sl_pct)
                ),
                "take_profit": (
                    current_price * (1 + tp_pct)
                    if prediction == 1
                    else current_price * (1 - tp_pct)
                ),
                "atr": atr,
                "mtf_1h": mtf["trend_1h"],
                "mtf_4h": mtf["trend_4h"],
                "mtf_strength": mtf["strength"],
            }

        except Exception as e:
            logger.error(f"[ERROR] Signal generation failed for {symbol}: {e}")
            return None

    def execute_trade(self, signal):
        """Execute trade with dynamic position sizing (LONG or SHORT)"""
        try:
            symbol = signal["symbol"]
            price = signal["price"]
            side = signal["side"]

            # ANTI-SPAM: Check if position already exists
            if symbol in self.positions:
                logger.warning(f"[ANTI-SPAM] Position already exists for {symbol}")
                logger.warning(
                    f"  Current: {self.positions[symbol]['side']} @ ${self.positions[symbol]['entry_price']:.2f}"
                )
                return False

            # ANTI-SPAM: Check recent trade cooldown
            current_time = time.time()
            if symbol in self.recent_trades:
                time_since_last = current_time - self.recent_trades[symbol]
                cooldown_remaining = self.trade_cooldown - time_since_last

                if cooldown_remaining > 0:
                    logger.warning(f"[ANTI-SPAM] Cooldown active for {symbol}")
                    logger.warning(f"  Last trade: {time_since_last:.0f}s ago")
                    logger.warning(f"  Wait: {cooldown_remaining:.0f}s more")
                    return False

            # ANTI-SPAM: Check failed attempts
            if (
                symbol in self.failed_attempts
                and self.failed_attempts[symbol] >= self.max_failed_attempts
            ):
                logger.warning(f"[ANTI-SPAM] Max failed attempts reached for {symbol}")
                logger.warning(f"  Failed: {self.failed_attempts[symbol]} times")
                logger.warning(f"  Extended cooldown: 30 minutes")
                # Check extended cooldown (30 min)
                if symbol in self.recent_trades:
                    if current_time - self.recent_trades[symbol] < 1800:  # 30 min
                        return False
                    else:
                        # Reset after extended cooldown
                        self.failed_attempts[symbol] = 0

            # ANTI-SPAM: Verify no pending orders for this symbol
            try:
                open_orders = self.exchange.fetch_open_orders(symbol)
                if open_orders:
                    logger.warning(
                        f"[ANTI-SPAM] Found {len(open_orders)} pending orders for {symbol}"
                    )
                    logger.warning(f"  Cancelling pending orders first...")
                    for order in open_orders:
                        self.exchange.cancel_order(order["id"], symbol)
                        logger.info(
                            f"  Cancelled: {order['type']} {order['side']} order {order['id']}"
                        )
                    time.sleep(1)  # Wait for cancellation to process
            except Exception as e:
                logger.error(f"[ERROR] Failed to check/cancel pending orders: {e}")

            # Calculate position size based on risk management
            # Get current balance
            balance = self.exchange.fetch_balance()
            total_usdc = balance["USDC"]["total"]

            # Calculate position size: Risk% / Stop Loss% = Position Size
            risk_pct = self.risk_per_trade_pct
            risk_amount = total_usdc * (risk_pct / 100)
            position_size = risk_amount / STOP_LOSS_PCT  # Total exposure

            # Margin needed (position / leverage)
            margin_needed = position_size / self.leverage

            # DEBUG: Log calculation details
            free_balance = balance["USDC"]["free"]
            logger.info(f"\n[MARGIN CHECK] Pre-trade validation:")
            logger.info(f"  Total Portfolio: ${total_usdc:,.2f}")
            logger.info(f"  Free Balance: ${free_balance:,.2f}")
            logger.info(f"  Used Balance: ${total_usdc - free_balance:,.2f}")
            logger.info(f"  Risk %: {risk_pct}%")
            logger.info(f"  Risk Amount: ${risk_amount:,.2f}")
            logger.info(f"  Position Size (exposure): ${position_size:,.2f}")
            logger.info(f"  Leverage: {self.leverage}x")
            logger.info(f"  Margin Needed: ${margin_needed:,.2f}")
            logger.info(f"  Open Positions: {len(self.positions)}")
            if self.positions:
                for sym, pos in self.positions.items():
                    logger.info(
                        f"    - {pos['side']} {sym}: ${pos['entry_price']:.2f} x {pos['amount']}"
                    )

            # SAFETY CHECK: Validate sufficient margin before opening position
            margin_with_buffer = margin_needed * 1.05  # 5% buffer for fees/slippage

            if margin_with_buffer > free_balance:
                # Check if we can reduce position size to fit available margin
                max_margin_available = free_balance * 0.95  # Use 95% of free balance
                max_position_size = max_margin_available * self.leverage

                # Only auto-adjust if we can get at least 50% of intended position
                if max_position_size >= (position_size * 0.5):
                    logger.warning(
                        f"\n⚠️ [AUTO-ADJUST] Insufficient margin for full position"
                    )
                    logger.warning(
                        f"  Intended: ${position_size:,.2f} → ${margin_needed:,.2f} margin"
                    )
                    logger.warning(
                        f"  Adjusted: ${max_position_size:,.2f} → ${max_margin_available:,.2f} margin"
                    )
                    logger.warning(
                        f"  Using {max_position_size/position_size*100:.0f}% of intended size"
                    )

                    # Update position size and margin
                    position_size = max_position_size
                    margin_needed = max_margin_available
                else:
                    logger.warning(f"\n⏸️ [SKIPPED] Insufficient margin for {symbol}")
                    logger.warning(
                        f"  Signal: {signal['confidence']*100:.1f}% confidence {side}"
                    )
                    logger.warning(
                        f"  Required: ${margin_with_buffer:,.2f} (margin with 5% buffer)"
                    )
                    logger.warning(f"  Available: ${free_balance:,.2f} (free balance)")
                    logger.warning(
                        f"  Shortfall: ${margin_with_buffer - free_balance:,.2f}"
                    )
                    logger.warning(f"  💡 Wait for existing position to close")
                    return False

            # Convert to amount in coins
            amount = position_size / price
            amount = self.exchange.amount_to_precision(symbol, amount)

            # Show priority status
            priority = "⭐ HIGH" if signal["confidence"] >= 0.65 else "📊 STANDARD"

            logger.info(f"\n[TRADE] Executing {side} {signal['action']} for {symbol}")
            logger.info(f"  Priority: {priority}")
            logger.info(f"  Entry Price: ${price:.2f}")
            logger.info(f"  Amount: {amount}")
            logger.info(f"  Position Value: ${position_size:.2f} (exposure)")
            logger.info(
                f"  Margin Required: ${margin_needed:.2f} ({margin_needed/total_usdc*100:.1f}% of portfolio)"
            )
            logger.info(f"  Risk Amount: ${risk_amount:.2f} ({risk_pct}% of portfolio)")
            logger.info(f"  Leverage: {self.leverage}x")
            logger.info(f"  Confidence: {signal['confidence']*100:.1f}%")
            logger.info(f"  Order Type: MARKET (instant execution)")

            # Place MARKET order for instant execution
            logger.info(f"[ORDER] Placing {side} MARKET order...")
            if side == "LONG":
                order = self.exchange.create_market_buy_order(symbol, amount)
            else:  # SHORT
                order = self.exchange.create_market_sell_order(symbol, amount)

            # Verify order was filled
            if not order or order.get("status") not in ["closed", "filled"]:
                logger.error(
                    f"[ERROR] Order not filled! Status: {order.get('status') if order else 'None'}"
                )
                logger.error(f"  Order details: {order}")
                # Increment failed attempts
                self.failed_attempts[symbol] = self.failed_attempts.get(symbol, 0) + 1
                # Set cooldown to prevent immediate retry
                self.recent_trades[symbol] = time.time()
                return False

            # Get filled price from order
            filled_price = (
                float(order.get("average", price)) if order.get("average") else price
            )
            filled_amount = float(order.get("filled", amount))
            logger.info(
                f"[FILLED] ✅ Order executed at ${filled_price:.2f} | Amount: {filled_amount}"
            )
            logger.info(f"  Order ID: {order.get('id', 'N/A')}")
            logger.info(f"  Status: {order.get('status', 'N/A')}")

            # Wait briefly for exchange to update position
            time.sleep(1)

            # Verify position exists on exchange before tracking
            logger.info(f"[VERIFY] Checking position on exchange...")
            time.sleep(0.5)  # Brief wait for position update

            try:
                exchange_positions = self.exchange.fetch_positions([symbol])
                position_found = False

                for pos in exchange_positions:
                    contracts = float(pos.get("contracts", 0))
                    if abs(contracts) > 0:
                        position_found = True
                        actual_side = "LONG" if contracts > 0 else "SHORT"
                        actual_entry = float(pos.get("entryPrice", filled_price))

                        logger.info(f"[VERIFY] ✅ Position confirmed on exchange")
                        logger.info(f"  Side: {actual_side} (expected: {side})")
                        logger.info(f"  Entry: ${actual_entry:.2f}")
                        logger.info(f"  Contracts: {abs(contracts)}")

                        # Use actual values from exchange
                        filled_price = actual_entry
                        filled_amount = abs(contracts)
                        break

                if not position_found:
                    logger.error(f"[ERROR] Position not found on exchange after order!")
                    logger.error(f"  Order was filled but position missing")
                    logger.error(f"  This indicates an exchange sync issue")
                    # Increment failed attempts
                    self.failed_attempts[symbol] = (
                        self.failed_attempts.get(symbol, 0) + 1
                    )
                    # Set cooldown
                    self.recent_trades[symbol] = time.time()
                    return False

            except Exception as e:
                logger.error(f"[ERROR] Failed to verify position: {e}")
                # Still track locally but mark as unverified
                logger.warning(
                    f"[WARNING] Tracking position locally without verification"
                )

            # Calculate ACTUAL TP/SL based on FILLED PRICE (not predicted price)
            # This ensures TP/SL are "lengket" (sticky) with actual entry
            logger.info(f"\n[TP/SL CALC] Calculating based on actual filled price...")

            if side == "LONG":
                actual_stop_loss = filled_price * (1 - STOP_LOSS_PCT)
                actual_take_profit = filled_price * (1 + TAKE_PROFIT_PCT)
                logger.info(f"  LONG Entry: ${filled_price:.2f}")
                logger.info(
                    f"  Stop Loss: ${actual_stop_loss:.2f} (-{STOP_LOSS_PCT*100}%)"
                )
                logger.info(
                    f"  Take Profit: ${actual_take_profit:.2f} (+{TAKE_PROFIT_PCT*100}%)"
                )
            else:  # SHORT
                actual_stop_loss = filled_price * (1 + STOP_LOSS_PCT)
                actual_take_profit = filled_price * (1 - TAKE_PROFIT_PCT)
                logger.info(f"  SHORT Entry: ${filled_price:.2f}")
                logger.info(
                    f"  Stop Loss: ${actual_stop_loss:.2f} (+{STOP_LOSS_PCT*100}%)"
                )
                logger.info(
                    f"  Take Profit: ${actual_take_profit:.2f} (-{TAKE_PROFIT_PCT*100}%)"
                )

            # Track position with ACTUAL TP/SL prices
            self.positions[symbol] = {
                "side": side,
                "entry_price": filled_price,
                "amount": float(filled_amount),
                "stop_loss": actual_stop_loss,
                "take_profit": actual_take_profit,
                "opened_at": datetime.now(),
                "confidence": signal["confidence"],
                "order_id": order.get("id", "N/A"),
            }

            # Record trade timestamp (anti-spam)
            self.recent_trades[symbol] = time.time()
            # Reset failed attempts on success
            self.failed_attempts[symbol] = 0

            # Set SL/TP orders on Binance server IMMEDIATELY - LENGKET dengan entry!
            logger.info(
                f"\n[PROTECTION] Setting server-side SL/TP orders IMMEDIATELY..."
            )
            logger.info(f"  Using ACTUAL filled price: ${filled_price:.2f}")
            try:
                sl_tp_success = self.set_server_side_orders(
                    symbol,
                    side,
                    float(filled_amount),  # Use actual filled amount
                    actual_stop_loss,  # Use calculated SL from filled price
                    actual_take_profit,  # Use calculated TP from filled price
                )

                if not sl_tp_success:
                    logger.error(f"[CRITICAL] Failed to set SL/TP orders!")
                    logger.error(
                        f"[CRITICAL] Closing position immediately for safety..."
                    )
                    # Close position immediately if SL/TP failed
                    try:
                        if side == "LONG":
                            self.exchange.create_market_sell_order(
                                symbol, filled_amount
                            )
                        else:
                            self.exchange.create_market_buy_order(symbol, filled_amount)
                        logger.info(f"[SAFETY] Position closed - SL/TP setup failed")
                        # Remove from tracking
                        del self.positions[symbol]
                    except Exception as close_err:
                        logger.error(f"[ERROR] Could not close position: {close_err}")
                    return False

                logger.info(
                    f"[PROTECTION] ✅ SL/TP orders successfully set and LINKED to entry!"
                )

            except Exception as e:
                logger.error(f"[CRITICAL] Exception setting SL/TP: {e}")
                logger.error(f"[CRITICAL] Closing position immediately for safety...")
                # Close position immediately if exception occurred
                try:
                    if side == "LONG":
                        self.exchange.create_market_sell_order(symbol, filled_amount)
                    else:
                        self.exchange.create_market_buy_order(symbol, filled_amount)
                    logger.info(f"[SAFETY] Position closed - SL/TP setup failed")
                    # Remove from tracking
                    del self.positions[symbol]
                except Exception as close_err:
                    logger.error(f"[ERROR] Could not close position: {close_err}")
                return False

            logger.info(
                f"[SUCCESS] Position opened: {side} {symbol} with SL/TP protection"
            )
            logger.info(
                f"[TP/SL] Prices calculated from actual fill: ${filled_price:.2f}"
            )
            logger.info(f"[COOLDOWN] Next trade for {symbol} allowed after 5 minutes")

            return True

        except Exception as e:
            logger.error(f"[ERROR] Trade execution failed: {e}")
            logger.error(f"  Exception type: {type(e).__name__}")
            logger.error(f"  Exception details: {str(e)}")

            # Record failed attempt
            self.failed_attempts[symbol] = self.failed_attempts.get(symbol, 0) + 1
            logger.warning(
                f"[FAILED] Attempt {self.failed_attempts[symbol]}/{self.max_failed_attempts}"
            )

            # Set cooldown even on failure to prevent spam
            self.recent_trades[symbol] = time.time()

            return False

    def set_server_side_orders(
        self, symbol, side, amount, stop_loss_price, take_profit_price
    ):
        """
        Set Stop Loss and Take Profit orders on Binance server with OCO behavior
        Using closePosition=true to ensure when one hits, the other auto-cancels

        Returns True if both orders successfully placed, False otherwise
        """
        try:
            logger.info(f"[SL/TP] Setting up protection orders...")
            logger.info(f"  Symbol: {symbol}")
            logger.info(f"  Side: {side}")
            logger.info(f"  Amount: {amount}")
            logger.info(f"  Stop Loss: ${stop_loss_price:.2f}")
            logger.info(f"  Take Profit: ${take_profit_price:.2f}")

            # For LONG position: SL sell below entry, TP sell above entry
            # For SHORT position: SL buy above entry, TP buy below entry

            if side == "LONG":
                # Stop Loss: STOP_MARKET sell order
                logger.info(f"[SL/TP] Creating STOP_MARKET sell order...")
                sl_order = self.exchange.create_order(
                    symbol=symbol,
                    type="STOP_MARKET",
                    side="sell",
                    amount=amount,
                    params={
                        "stopPrice": stop_loss_price,
                        "reduceOnly": True,  # Only close position, don't open new
                        "closePosition": True,  # Close entire position (auto-cancel other orders)
                    },
                )
                logger.info(
                    f"[SL ORDER] ✅ STOP MARKET @ ${stop_loss_price:.2f} (ID: {sl_order.get('id', 'N/A')})"
                )

                # Take Profit: TAKE_PROFIT_MARKET sell order
                logger.info(f"[SL/TP] Creating TAKE_PROFIT_MARKET sell order...")
                tp_order = self.exchange.create_order(
                    symbol=symbol,
                    type="TAKE_PROFIT_MARKET",
                    side="sell",
                    amount=amount,
                    params={
                        "stopPrice": take_profit_price,
                        "reduceOnly": True,
                        "closePosition": True,  # Close entire position (auto-cancel other orders)
                    },
                )
                logger.info(
                    f"[TP ORDER] ✅ TAKE PROFIT MARKET @ ${take_profit_price:.2f} (ID: {tp_order.get('id', 'N/A')})"
                )

            else:  # SHORT
                # Stop Loss: STOP_MARKET buy order
                logger.info(f"[SL/TP] Creating STOP_MARKET buy order...")
                sl_order = self.exchange.create_order(
                    symbol=symbol,
                    type="STOP_MARKET",
                    side="buy",
                    amount=amount,
                    params={
                        "stopPrice": stop_loss_price,
                        "reduceOnly": True,
                        "closePosition": True,  # Close entire position (auto-cancel other orders)
                    },
                )
                logger.info(
                    f"[SL ORDER] ✅ STOP MARKET @ ${stop_loss_price:.2f} (ID: {sl_order.get('id', 'N/A')})"
                )

                # Take Profit: TAKE_PROFIT_MARKET buy order
                logger.info(f"[SL/TP] Creating TAKE_PROFIT_MARKET buy order...")
                tp_order = self.exchange.create_order(
                    symbol=symbol,
                    type="TAKE_PROFIT_MARKET",
                    side="buy",
                    amount=amount,
                    params={
                        "stopPrice": take_profit_price,
                        "reduceOnly": True,
                        "closePosition": True,  # Close entire position (auto-cancel other orders)
                    },
                )
                logger.info(
                    f"[TP ORDER] ✅ TAKE PROFIT MARKET @ ${take_profit_price:.2f} (ID: {tp_order.get('id', 'N/A')})"
                )

            logger.info(
                f"[SERVER PROTECTION] ✅ SL/TP orders LINKED (OCO-like behavior)"
            )
            logger.info(
                f"  💡 When TP hits → SL auto-cancels | When SL hits → TP auto-cancels"
            )
            return True

        except Exception as e:
            logger.error(f"[ERROR] Failed to set server-side orders: {e}")
            logger.error(f"[ERROR] Exception type: {type(e).__name__}")
            logger.error(f"[ERROR] Exception details: {str(e)}")
            return False

    def cancel_server_side_orders(self, symbol):
        """Cancel all open orders for a symbol (SL/TP cleanup)"""
        try:
            # Get all open orders for this symbol
            logger.info(f"[CLEANUP] Fetching open orders for {symbol}...")
            open_orders = self.exchange.fetch_open_orders(symbol)

            if not open_orders:
                logger.info(f"[CLEANUP] ✅ No pending orders to cancel for {symbol}")
                return True

            logger.info(
                f"[CLEANUP] Found {len(open_orders)} open order(s) for {symbol}"
            )

            # Cancel each order
            cancelled_count = 0
            for order in open_orders:
                try:
                    order_id = order["id"]
                    order_type = order.get("type", "UNKNOWN")
                    order_side = order.get("side", "UNKNOWN")

                    logger.info(
                        f"[CLEANUP] Cancelling {order_type} {order_side} order {order_id}..."
                    )
                    self.exchange.cancel_order(order_id, symbol)
                    logger.info(f"[CLEANUP] ✅ Cancelled {order_type} order {order_id}")
                    cancelled_count += 1
                except Exception as e:
                    logger.error(f"[ERROR] Could not cancel order {order_id}: {e}")

            logger.info(
                f"[CLEANUP] ✅ Cancelled {cancelled_count}/{len(open_orders)} order(s) for {symbol}"
            )
            return True

        except Exception as e:
            logger.error(f"[ERROR] Failed to cancel orders for {symbol}: {e}")
            return False

    def check_positions(self):
        """Monitor open positions and update trailing stops"""
        # Safety Layer 1: Full sync with Binance positions
        try:
            binance_positions = self.exchange.fetch_positions()
            active_positions = {}

            for p in binance_positions:
                if float(p.get("contracts", 0)) > 0:
                    # Normalize symbol format (remove :USDC suffix if present)
                    symbol = p["symbol"]
                    if ":USDC" in symbol and symbol.endswith(":USDC"):
                        symbol = symbol.replace(":USDC", "")
                    active_positions[symbol] = p

            # Remove positions that were closed externally
            for symbol in list(self.positions.keys()):
                if symbol not in active_positions:
                    logger.warning(
                        f"[SYNC] Position {symbol} closed externally. Removing from tracking."
                    )

                    # Cancel any pending TP/SL orders for this symbol
                    try:
                        logger.info(
                            f"[CLEANUP] Cancelling orphan orders for {symbol}..."
                        )
                        self.cancel_server_side_orders(symbol)
                    except Exception as e:
                        logger.warning(
                            f"[WARNING] Could not cancel orders for {symbol}: {e}"
                        )

                    del self.positions[symbol]

            # Add positions that exist on Binance but not in bot tracking
            for symbol, binance_pos in active_positions.items():
                if symbol not in self.positions:
                    contracts = float(binance_pos.get("contracts", 0))
                    entry_price = float(binance_pos.get("entryPrice", 0))
                    side = "LONG" if contracts > 0 else "SHORT"

                    logger.warning(f"[SYNC] Found untracked position: {side} {symbol}")
                    logger.warning(
                        f"       Entry: ${entry_price:.2f}, Amount: {abs(contracts)}"
                    )

                    # Add to tracking with default TP/SL
                    self.positions[symbol] = {
                        "side": side,
                        "entry_price": entry_price,
                        "amount": abs(contracts),
                        "stop_loss": entry_price * (0.98 if side == "LONG" else 1.02),
                        "take_profit": entry_price * (1.04 if side == "LONG" else 0.96),
                        "opened_at": datetime.now(),
                        "confidence": 0.0,  # Unknown confidence
                    }
                    logger.info(f"[SYNC] Added {symbol} to tracking with default TP/SL")

        except Exception as e:
            logger.error(f"[ERROR] Position sync failed: {e}")

        for symbol, pos in list(self.positions.items()):
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker["last"]

                entry_price = pos["entry_price"]
                side = pos["side"]

                # Calculate P&L (inverse for SHORT)
                if side == "LONG":
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:  # SHORT
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100

                logger.info(
                    f"[POSITION] {side} {symbol}: ${current_price:.2f} | P&L: {pnl_pct:+.2f}%"
                )

                # Update trailing stop if in profit
                if pnl_pct > 1.0:  # At least 1% profit
                    if side == "LONG":
                        # LONG: New trailing SL = current price - 2%
                        trailing_sl = current_price * (1 - STOP_LOSS_PCT)
                        if trailing_sl > pos["stop_loss"]:
                            old_sl = pos["stop_loss"]
                            pos["stop_loss"] = trailing_sl
                            logger.info(
                                f"[TRAILING SL] {symbol}: ${old_sl:.2f} → ${trailing_sl:.2f} (Locked {pnl_pct:.1f}% profit)"
                            )
                    else:  # SHORT
                        # SHORT: New trailing SL = current price + 2%
                        trailing_sl = current_price * (1 + STOP_LOSS_PCT)
                        if trailing_sl < pos["stop_loss"]:  # Lower is better for SHORT
                            old_sl = pos["stop_loss"]
                            pos["stop_loss"] = trailing_sl
                            logger.info(
                                f"[TRAILING SL] {symbol}: ${old_sl:.2f} → ${trailing_sl:.2f} (Locked {pnl_pct:.1f}% profit)"
                            )

                # Check stop loss and take profit (logic depends on LONG vs SHORT)
                if side == "LONG":
                    if current_price <= pos["stop_loss"]:
                        logger.warning(f"[STOP LOSS] Triggered for {symbol}")
                        self.close_position(symbol, current_price, "STOP_LOSS")
                    elif current_price >= pos["take_profit"]:
                        logger.info(f"[TAKE PROFIT] Triggered for {symbol}")
                        self.close_position(symbol, current_price, "TAKE_PROFIT")
                else:  # SHORT
                    if current_price >= pos["stop_loss"]:
                        logger.warning(f"[STOP LOSS] Triggered for {symbol}")
                        self.close_position(symbol, current_price, "STOP_LOSS")
                    elif current_price <= pos["take_profit"]:
                        logger.info(f"[TAKE PROFIT] Triggered for {symbol}")
                        self.close_position(symbol, current_price, "TAKE_PROFIT")

            except Exception as e:
                logger.error(f"[ERROR] Position check failed for {symbol}: {e}")

    def close_position(self, symbol, price, reason):
        """Close position with LIMIT order and save to database"""
        try:
            # Safety Layer 2: Validate position exists in memory
            if symbol not in self.positions:
                logger.warning(f"[SKIP] Position {symbol} not found in tracking")
                return

            pos = self.positions[symbol]
            amount = float(pos["amount"])
            side = pos["side"]

            # Safety Layer 3: Check if position still exists on Binance
            try:
                binance_positions = self.exchange.fetch_positions([symbol])
                position_exists = any(
                    float(p.get("contracts", 0)) > 0
                    for p in binance_positions
                    if p["symbol"] == symbol
                )

                if not position_exists:
                    logger.warning(
                        f"[SKIP] {symbol} already closed on exchange. Removing from tracking."
                    )
                    del self.positions[symbol]
                    return
            except Exception as e:
                logger.warning(
                    f"[WARNING] Could not verify position on exchange: {e}. Proceeding..."
                )

            logger.info(f"[CLOSING] {side} {symbol} - {reason}")

            # Cancel any pending SL/TP orders FIRST (before closing position)
            # This ensures cleanup happens even if close fails
            try:
                logger.info(
                    f"[CLEANUP] Cancelling pending TP/SL orders for {symbol}..."
                )
                self.cancel_server_side_orders(symbol)
            except Exception as e:
                logger.warning(f"[WARNING] Could not cancel server-side orders: {e}")

            # Safety Layer 4: Try close with error handling
            try:
                if side == "LONG":
                    order = self.exchange.create_market_sell_order(symbol, amount)
                else:  # SHORT
                    order = self.exchange.create_market_buy_order(symbol, amount)
            except Exception as order_error:
                # Handle insufficient balance / position not found errors
                error_msg = str(order_error).lower()
                if (
                    "insufficient" in error_msg
                    or "balance" in error_msg
                    or "position" in error_msg
                ):
                    logger.warning(
                        f"[SKIP] {symbol} - Position likely closed manually: {order_error}"
                    )
                    del self.positions[symbol]
                    return
                else:
                    raise  # Re-raise if it's a different error

            # Get exit price from order
            exit_price = (
                float(order.get("average", price)) if order.get("average") else price
            )

            # Calculate P&L
            if side == "LONG":
                pnl = (exit_price - pos["entry_price"]) * amount
                pnl_pct = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100
            else:  # SHORT
                pnl = (pos["entry_price"] - exit_price) * amount
                pnl_pct = ((pos["entry_price"] - exit_price) / pos["entry_price"]) * 100

            # Update total P&L
            self.total_pnl += pnl
            self.daily_pnl += pnl

            # Get current balance for portfolio impact
            balance = self.exchange.fetch_balance()
            current_portfolio = balance["total"].get("USDC", 0)
            portfolio_impact_pct = (
                (pnl / self.initial_balance) * 100 if self.initial_balance > 0 else 0
            )

            logger.info(f"[CLOSED] {side} {symbol} - {reason}")
            logger.info(f"  Entry: ${pos['entry_price']:.2f}")
            logger.info(f"  Exit: ${exit_price:.2f}")
            logger.info(f"  Trade P&L: ${pnl:+.2f} ({pnl_pct:+.2f}% of position)")
            logger.info(
                f"  Portfolio Impact: {portfolio_impact_pct:+.2f}% (from ${self.initial_balance:.2f} initial)"
            )
            logger.info(f"  New Balance: ${current_portfolio:.2f}")
            logger.info(f"  Session Total P&L: ${self.total_pnl:+,.2f}")

            # Calculate duration
            duration = (datetime.now() - pos["opened_at"]).seconds

            # Save trade to database
            trade_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "action": side,
                "entry_price": pos["entry_price"],
                "exit_price": exit_price,
                "quantity": amount,
                "confidence": pos.get("confidence", 0),
                "stop_loss": pos["stop_loss"],
                "take_profit": pos["take_profit"],
                "exit_reason": reason,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "leverage": self.leverage,
                "duration": duration,
            }
            self.save_trade(trade_data)

            # Update streaks for position sizing
            if pnl > 0:
                self.win_streak += 1
                self.loss_streak = 0
            else:
                self.loss_streak += 1
                self.win_streak = 0

            # Add to trade history for Kelly Criterion
            self.trade_history.append(trade_data)

            del self.positions[symbol]

        except ccxt.InsufficientFunds as e:
            logger.warning(
                f"[SKIP] {symbol} - Insufficient funds (likely closed manually): {e}"
            )
            if symbol in self.positions:
                del self.positions[symbol]
        except ccxt.InvalidOrder as e:
            logger.warning(
                f"[SKIP] {symbol} - Invalid order (position may be closed): {e}"
            )
            if symbol in self.positions:
                del self.positions[symbol]
        except Exception as e:
            logger.error(f"[ERROR] Failed to close {symbol}: {e}")
            logger.error(f"[ERROR] Keeping position in tracking for retry")

    def run_forever(self):
        """Main 24/7 trading loop"""
        logger.info("\n[START] Bot started - Running 24/7")
        logger.info("[START] Press Ctrl+C to stop\n")

        consecutive_errors = 0
        last_display_time = time.time()

        # Print header once
        print("\n" + "=" * 80)
        print(" 🤖 AI TRADING BOT - LIVE MONITORING")
        print("=" * 80)
        print("Press Ctrl+C to stop\n")

        while True:
            try:
                # Clear screen and reposition cursor for real-time update
                if os.name == "nt":  # Windows
                    os.system("cls")
                else:  # Unix/Linux/Mac
                    os.system("clear")

                # Print live status header
                print("\n" + "=" * 80)
                print(
                    f" 🤖 AI TRADING BOT - LIVE [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]"
                )
                print("=" * 80 + "\n")

                # Check if model needs retraining (every 7 days)
                if self.should_retrain():
                    logger.info(
                        "\n[RETRAIN] 7 days since last training - Retraining model..."
                    )
                    self.retrain_model()

                # Reset daily P&L at midnight
                if datetime.now().date() != self.today_date:
                    logger.info(f"\n[DAILY] Yesterday P&L: ${self.daily_pnl:+,.2f}")
                    self.daily_pnl = 0.0
                    self.today_date = datetime.now().date()

                # Show live P&L (every cycle for real-time display)
                self.show_balance()

                # Check existing positions
                if self.positions:
                    logger.info(
                        f"\n[MONITOR] Checking {len(self.positions)} position(s)"
                    )
                    # Show current positions
                    for sym, pos in self.positions.items():
                        current_price = self.exchange.fetch_ticker(sym)["last"]
                        # Fix P&L calculation for SHORT positions
                        if pos["side"] == "SHORT":
                            pnl_pct = (
                                (pos["entry_price"] - current_price)
                                / pos["entry_price"]
                            ) * 100
                        else:  # LONG
                            pnl_pct = (
                                (current_price - pos["entry_price"])
                                / pos["entry_price"]
                            ) * 100

                        # Calculate dollar P&L
                        position_value = float(pos["amount"]) * float(
                            pos["entry_price"]
                        )
                        pnl_dollar = position_value * (pnl_pct / 100)

                        logger.info(
                            f"  • {pos['side']} {sym}: ${pos['entry_price']:.2f} → ${current_price:.2f} | P&L: {pnl_pct:+.2f}% (${pnl_dollar:+.2f})"
                        )

                    self.check_positions()
                else:
                    logger.info("\n[MONITOR] No open positions")

                # Generate new signals if positions available
                if len(self.positions) < MAX_POSITIONS:
                    logger.info(f"\n[SCAN] Scanning for signals...")

                    # Collect all signals
                    all_signals = []
                    for symbol in SYMBOLS:
                        if symbol not in self.positions:
                            signal = self.generate_signal(symbol)
                            if signal:
                                all_signals.append(signal)

                    if all_signals:
                        # Sort by confidence (highest first)
                        all_signals.sort(key=lambda x: x["confidence"], reverse=True)

                        # Display ALL signals
                        logger.info(f"\n[SIGNALS] Found {len(all_signals)} signal(s):")
                        for sig in all_signals:
                            logger.info(
                                f"  {sig['status']} {sig['symbol']}: {sig['confidence']*100:.1f}% - {sig['reason']}"
                            )
                            logger.info(
                                f"    Price: ${sig['price']:.2f} | Buy: {sig['proba_buy']*100:.0f}% | Sell: {sig['proba_sell']*100:.0f}%"
                            )
                            logger.info(
                                f"    SL: ${sig['stop_loss']:.2f} | TP: ${sig['take_profit']:.2f}"
                            )
                            logger.info(
                                f"    MTF: 1H={sig['mtf_1h']}, 4H={sig['mtf_4h']}, Strength={sig['mtf_strength']}"
                            )

                        # Execute only executable signals (≥40%)
                        logger.info(f"\n[EXECUTION] Processing executable signals...")
                        executed = False
                        for sig in all_signals:
                            if sig["executable"]:
                                logger.info(
                                    f"  ✓ Executing: {sig['symbol']} ({sig['confidence']*100:.1f}%)"
                                )
                                if self.execute_trade(sig):
                                    consecutive_errors = 0
                                    executed = True
                                    time.sleep(2)  # Delay between trades
                            else:
                                logger.info(
                                    f"  ✗ Skipped: {sig['symbol']} - {sig['reason']}"
                                )

                        if not executed:
                            logger.info(
                                "  No executable signals found (all below threshold)"
                            )
                    else:
                        logger.info("  No signals detected")

                # Reset error counter on successful cycle
                consecutive_errors = 0

                # Wait before next cycle (1 second for real-time updates)
                time.sleep(1)

            except KeyboardInterrupt:
                logger.info("\n[STOP] Bot stopped by user")
                break

            except Exception as e:
                consecutive_errors += 1
                logger.error(f"\n[ERROR] Cycle failed: {e}")
                logger.error(traceback.format_exc())

                if consecutive_errors >= 5:
                    logger.critical(
                        "[CRITICAL] Too many consecutive errors! Stopping bot."
                    )
                    break

                logger.info(
                    f"[RECOVERY] Waiting 60s before retry... ({consecutive_errors}/5)"
                )
                time.sleep(60)

        logger.info("\n[EXIT] Bot shutdown complete")


def select_leverage():
    """Interactive leverage selector"""
    print("\n" + "=" * 80)
    print(" 🚀 LEVERAGE SELECTOR")
    print("=" * 80)
    print("\nPilih leverage untuk trading:")
    print("  [1] 1x  - Spot Trading (Aman, no liquidation risk)")
    print("  [2] 3x  - Conservative Leverage (Rendah risk)")
    print("  [3] 5x  - Moderate Leverage (Medium risk)")
    print("  [4] 10x - Aggressive Leverage (High risk) ⚠️")
    print("  [5] 20x - Extreme Leverage (Very high risk) ⚠️⚠️")

    leverage_map = {1: 1, 2: 3, 3: 5, 4: 10, 5: 20}

    while True:
        try:
            choice = int(input("\nMasukkan pilihan (1-5): "))
            if choice in leverage_map:
                leverage = leverage_map[choice]
                print(f"\n✅ Leverage dipilih: {leverage}x")

                if leverage > 5:
                    confirm = input(
                        f"⚠️  PERHATIAN: Leverage {leverage}x sangat berisiko! Lanjutkan? (yes/no): "
                    )
                    if confirm.lower() != "yes":
                        print("Leverage dibatalkan. Memilih 1x (spot).")
                        return 1

                return leverage
            else:
                print("❌ Pilihan tidak valid. Pilih 1-5.")
        except ValueError:
            print("❌ Input tidak valid. Masukkan angka 1-5.")
        except KeyboardInterrupt:
            print("\n❌ Dibatalkan. Menggunakan 1x (spot).")
            return 1


def select_risk_per_trade():
    """Interactive risk per trade selector"""
    print("\n" + "=" * 80)
    print(" 💰 RISK MANAGEMENT")
    print("=" * 80)
    print("\nBerapa % dari portfolio yang ingin Anda risikokan per trade?")
    print("Example: 2% berarti jika portfolio $1000, setiap trade risiko $20")
    print("\nRekomendasi:")
    print("  • Conservative: 1-2% (Aman, growth lambat)")
    print("  • Moderate: 2-3% (Balanced)")
    print("  • Aggressive: 3-5% (High risk, high reward) ⚠️")
    print("  • Very Aggressive: 5-10% (Sangat berisiko!) ⚠️⚠️")
    print("  • EXTREME: >10% (BAHAYA! Bisa habis cepat!) ⚠️⚠️⚠️")

    while True:
        try:
            risk_input = input(
                "\nRisk per trade (% dari portfolio, default 2): "
            ).strip()
            if not risk_input:
                risk_pct = 2.0
            else:
                risk_pct = float(risk_input)

            if risk_pct <= 0 or risk_pct > 50:
                print("❌ Risk harus antara 0.1% - 50%. Silakan coba lagi.")
                continue

            print(f"\n✅ Risk per trade: {risk_pct}%")

            if risk_pct > 5:
                confirm = input(
                    f"⚠️  PERHATIAN: Risk {risk_pct}% sangat tinggi! Anda bisa kehilangan portfolio cepat. Lanjutkan? (yes/no): "
                )
                if confirm.lower() != "yes":
                    print("Risk dibatalkan. Menggunakan 2% (default).")
                    return 2.0

            return risk_pct
        except ValueError:
            print("❌ Input tidak valid. Masukkan angka (contoh: 2 atau 2.5).")
        except KeyboardInterrupt:
            print("\n❌ Dibatalkan. Menggunakan 2% (default).")
            return 2.0


if __name__ == "__main__":
    # Interactive leverage selection
    leverage = select_leverage()

    # Interactive risk per trade selection
    risk_per_trade = select_risk_per_trade()

    # Start bot with selected parameters
    bot = InstitutionalTradingBot(leverage=leverage, risk_per_trade_pct=risk_per_trade)
    bot.run_forever()
