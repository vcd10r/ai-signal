"""
Fetch real market data from Binance API
"""

import pandas as pd
import ccxt
import warnings

warnings.filterwarnings("ignore")


def fetch_real_market_data(
    symbol: str, timeframe: str = "1h", limit: int = 500
) -> pd.DataFrame:
    """
    Fetch real market data from Binance

    Args:
        symbol: Trading pair (e.g., "BTC/USDT")
        timeframe: Candle timeframe (e.g., "1h", "4h")
        limit: Number of candles to fetch (default 500)

    Returns:
        DataFrame with OHLCV data
    """
    try:
        exchange = ccxt.binance({"enableRateLimit": True})

        # Fetch OHLCV data
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        # Convert to DataFrame
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        # Set index and sort
        df = df.set_index("timestamp").sort_index()

        # Ensure data is not empty
        if len(df) == 0:
            raise ValueError(f"No data fetched for {symbol}")

        return df

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame()


def generate_signal_with_levels(
    entry: float, atr: float, risk_reward: float = 2.0
) -> dict:
    """
    Generate signal with SL and TP based on entry and ATR

    Args:
        entry: Entry price
        atr: Average True Range value
        risk_reward: Risk to Reward ratio (default 2.0)

    Returns:
        Dictionary with entry, stop_loss, take_profit, risk_per_trade, reward_per_trade
    """
    # Calculate stop loss (ATR * 1.5 below entry)
    stop_loss = entry - (atr * 1.5)

    # Calculate risk
    risk_per_trade = entry - stop_loss

    # Calculate reward (risk * reward_ratio)
    reward_per_trade = risk_per_trade * risk_reward

    # Calculate take profit
    take_profit = entry + reward_per_trade

    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_per_trade": risk_per_trade,
        "reward_per_trade": reward_per_trade,
        "risk_reward_ratio": risk_reward,
    }
