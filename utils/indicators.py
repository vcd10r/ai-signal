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
    atr = tr.rolling(window=period).mean()
    return atr
