import pandas as pd
import numpy as np


def calculate_sma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Simple Moving Average"""
    return df["close"].rolling(window=period).mean()


def calculate_ema(df: pd.DataFrame, period: int = 12) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return df["close"].ewm(span=period, adjust=False).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index"""
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(df: pd.DataFrame) -> tuple:
    """Calculate MACD"""
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return macd, signal, histogram


def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20) -> tuple:
    """Calculate Bollinger Bands"""
    sma = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    upper = sma + (std * 2)
    lower = sma - (std * 2)
    return upper, sma, lower


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


# ============================================================================
# INSTITUTIONAL INDICATORS (Smart Money Detection)
# ============================================================================


def calculate_order_flow(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Cumulative Volume Delta (CVD) - Order Flow
    Detects where institutions accumulate/distribute
    """
    df = df.copy()

    # Volume delta (positive when close > open, negative otherwise)
    df["volume_delta"] = df["volume"] * np.where(df["close"] > df["open"], 1, -1)

    # Cumulative Volume Delta (CVD)
    df["cvd"] = df["volume_delta"].cumsum()
    df["cvd_slope"] = df["cvd"].pct_change(5)

    # Buy/Sell pressure
    df["buy_volume"] = df["volume"].where(df["close"] > df["open"], 0)
    df["sell_volume"] = df["volume"].where(df["close"] <= df["open"], 0)

    # Buy/Sell ratio (institutional bias)
    df["buy_sell_ratio"] = df["buy_volume"].rolling(20).sum() / (
        df["sell_volume"].rolling(20).sum() + 1e-10
    )

    return df


def detect_market_structure(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """
    Detect Market Structure (Swing Highs/Lows)
    Smart money respects key levels
    """
    df = df.copy()

    # Swing highs and lows
    df["swing_high"] = df["high"].rolling(lookback).max()
    df["swing_low"] = df["low"].rolling(lookback).min()

    # Structure break detection
    df["structure_break_up"] = (df["close"] > df["swing_high"].shift(1)).astype(int)
    df["structure_break_down"] = (df["close"] < df["swing_low"].shift(1)).astype(int)

    # Distance from structure levels (%)
    df["dist_from_high"] = (df["swing_high"] - df["close"]) / df["close"]
    df["dist_from_low"] = (df["close"] - df["swing_low"]) / df["close"]

    return df


def identify_liquidity_zones(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify Liquidity Zones - Where stop hunts happen
    Institutions target stop-loss clusters
    """
    df = df.copy()

    # High liquidity events (volume spike + price rejection)
    avg_volume = df["volume"].rolling(50).mean()
    df["high_liquidity"] = (df["volume"] > avg_volume * 2).astype(int)

    # Price rejection candles (long wicks)
    body = abs(df["close"] - df["open"])
    total_range = df["high"] - df["low"]
    df["price_rejection"] = (body / (total_range + 1e-10) < 0.3).astype(int)

    # Liquidity grab (high volume + rejection)
    df["liquidity_grab"] = (df["high_liquidity"] * df["price_rejection"]).astype(int)

    return df


def detect_institutional_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect Institutional Candle Patterns
    Candles that show smart money activity
    """
    df = df.copy()

    body = abs(df["close"] - df["open"])
    total_range = df["high"] - df["low"]
    upper_wick = df["high"] - df[["close", "open"]].max(axis=1)
    lower_wick = df[["close", "open"]].min(axis=1) - df["low"]

    # Pin bar (rejection candle)
    df["pin_bar"] = (
        (body / (total_range + 1e-10) < 0.3)
        & ((upper_wick > body * 2) | (lower_wick > body * 2))
    ).astype(int)

    # Engulfing pattern (strong momentum)
    df["engulfing"] = (body > body.shift(1) * 1.5).astype(int)

    # Doji (indecision)
    df["doji"] = (body / (total_range + 1e-10) < 0.1).astype(int)

    # Strong momentum candle
    df["strong_candle"] = (body > body.rolling(20).mean() * 1.5).astype(int)

    return df


def calculate_fair_value_gap(df: pd.DataFrame, lookback: int = 100) -> pd.DataFrame:
    """
    Calculate Premium/Discount Zones (Fair Value Gap)
    Institutions trade at discount, retail buys premium
    """
    df = df.copy()

    # Recent range
    recent_high = df["high"].rolling(lookback).max()
    recent_low = df["low"].rolling(lookback).min()

    # Current position in range (0 = low, 1 = high)
    current_range = (df["close"] - recent_low) / (recent_high - recent_low + 1e-10)

    # Premium/Discount classification
    df["in_discount"] = (current_range < 0.3).astype(int)  # Buy zone (lower 30%)
    df["in_equilibrium"] = ((current_range >= 0.3) & (current_range <= 0.7)).astype(int)
    df["in_premium"] = (current_range > 0.7).astype(int)  # Sell zone (upper 30%)

    # Fair value score (-1 = discount, 0 = equilibrium, 1 = premium)
    df["fair_value_score"] = current_range * 2 - 1

    return df


def calculate_institutional_composite(df: pd.DataFrame) -> pd.DataFrame:
    """
    Composite Institutional Score
    Combines all smart money indicators into one score
    """
    df = df.copy()

    # Apply all institutional indicators
    df = calculate_order_flow(df)
    df = detect_market_structure(df)
    df = identify_liquidity_zones(df)
    df = detect_institutional_candles(df)
    df = calculate_fair_value_gap(df)

    # Normalize scores to -1 to 1 range
    cvd_norm = df["cvd_slope"].fillna(0).clip(-0.1, 0.1) / 0.1
    structure_norm = df["structure_break_up"] - df["structure_break_down"]
    liquidity_norm = df["liquidity_grab"]
    candle_norm = (df["pin_bar"] + df["engulfing"] + df["strong_candle"]) / 3
    fvg_norm = df["fair_value_score"].fillna(0)

    # Weighted composite score
    df["institutional_score"] = (
        cvd_norm * 0.25  # Order flow weight
        + structure_norm * 0.25  # Market structure weight
        + liquidity_norm * 0.15  # Liquidity zones weight
        + candle_norm * 0.15  # Candle patterns weight
        + fvg_norm * 0.20  # Fair value gap weight
    )

    # Institutional bias (BULLISH, BEARISH, NEUTRAL)
    df["institutional_bias"] = np.where(
        df["institutional_score"] > 0.3,
        1,  # BULLISH
        np.where(df["institutional_score"] < -0.3, -1, 0),  # BEARISH / NEUTRAL
    )

    return df
    atr = tr.rolling(window=period).mean()
    return atr
