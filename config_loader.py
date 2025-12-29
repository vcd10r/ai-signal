"""
Config loader - reads from api_config.txt
"""
from pathlib import Path

def load_config():
    """Load configuration from api_config.txt"""
    config = {}
    config_file = Path("api_config.txt")
    
    if not config_file.exists():
        raise FileNotFoundError(
            "api_config.txt not found! Copy api_config.txt.example and fill in your API keys."
        )
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove inline comments (everything after #)
                    value = value.split('#')[0].strip()
                    config[key.strip()] = value
    
    # Convert types
    config['MIN_CONFIDENCE'] = float(config.get('MIN_CONFIDENCE', 0.40))
    config['POSITION_SIZE_USD'] = float(config.get('POSITION_SIZE_USD', 50))
    config['RISK_PER_TRADE_PCT'] = float(config.get('RISK_PER_TRADE_PCT', 2.0))  # New: risk per trade
    config['MAX_POSITIONS'] = int(config.get('MAX_POSITIONS', 2))
    config['STOP_LOSS_PCT'] = float(config.get('STOP_LOSS_PCT', 0.02))
    config['TAKE_PROFIT_PCT'] = float(config.get('TAKE_PROFIT_PCT', 0.04))
    config['CHECK_INTERVAL'] = int(config.get('CHECK_INTERVAL', 300))
    config['SYMBOLS'] = [s.strip() for s in config.get('SYMBOLS', 'BTC/USDC,ETH/USDC').split(',')]
    
    return config

# Load config
CONFIG = load_config()

# Export for backwards compatibility
API_KEY = CONFIG['BINANCE_API_KEY']
API_SECRET = CONFIG['BINANCE_API_SECRET']
MIN_CONFIDENCE = CONFIG['MIN_CONFIDENCE']
POSITION_SIZE_USD = CONFIG.get('POSITION_SIZE_USD', 50)
RISK_PER_TRADE_PCT = CONFIG.get('RISK_PER_TRADE_PCT', 2.0)  # New: risk per trade %
MAX_POSITIONS = CONFIG['MAX_POSITIONS']
STOP_LOSS_PCT = CONFIG['STOP_LOSS_PCT']
TAKE_PROFIT_PCT = CONFIG['TAKE_PROFIT_PCT']
CHECK_INTERVAL = CONFIG['CHECK_INTERVAL']
SYMBOLS = CONFIG['SYMBOLS']

# Defaults
TIMEFRAME = "1h"
LOOKBACK_DAYS = 70
LOG_LEVEL = "INFO"
LOG_FILE = "trading_bot_24_7.log"
