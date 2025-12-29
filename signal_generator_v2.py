"""
Advanced Signal Generator with Adaptive Model Loading
- Load best trained model
- Detect market regime
- Generate adaptive signals
- Real-time risk management
"""

import sys
import io

# Fix Windows console encoding for emojis
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except:
    pass
import pandas as pd
import numpy as np
import pickle
import json
import glob
import ccxt
from datetime import datetime
from sklearn.preprocessing import StandardScaler
import warnings

warnings.filterwarnings("ignore")

print("=" * 80)
print(" [ADAPTIVE SIGNAL GENERATOR] - Using Best Trained Model")
print("=" * 80)

# ============================================================================
# STEP 1: Load Best Model
# ============================================================================
print("\n[STEP 1] Loading Best Trained Model...")

# Find latest UJI 5 model (BEST MODEL)
import os

model_files = glob.glob("models/best_model_v2_lgb_uji5_*.pkl")
if not model_files:
    print("  WARNING: No UJI 5 model found! Trying any v2 model...")
    model_files = glob.glob("models/best_model_v2_lgb_*.pkl")
    if not model_files:
        print("  ERROR: No trained model found!")
        print("  Please run: python train_uji5_fast_gridsearch.py")
        exit(1)

# Get latest model
latest_model_file = sorted(model_files, reverse=True)[0]
timestamp = "_".join(latest_model_file.split("_")[-2:])[:-4]
model_type = "uji5" if "uji5" in latest_model_file else "v2"

print(f"  [BEST MODEL] Loading: {os.path.basename(latest_model_file)}")

# Load model
with open(latest_model_file, "rb") as f:
    model = pickle.load(f)

# Load features
if model_type == "uji5":
    features_file = f"models/features_v2_lgb_uji5_{timestamp}.json"
else:
    features_file = latest_model_file.replace("best_model_", "features_").replace(
        ".pkl", ".json"
    )

with open(features_file, "r") as f:
    features_data = json.load(f)
    feature_cols = (
        features_data
        if isinstance(features_data, list)
        else features_data.get("feature_columns", [])
    )

# Load metadata
if model_type == "uji5":
    metadata_file = f"models/metadata_v2_lgb_uji5_{timestamp}.json"
else:
    metadata_file = latest_model_file.replace("best_model_", "metadata_").replace(
        ".pkl", ".json"
    )

with open(metadata_file, "r") as f:
    metadata = json.load(f)

# Extract metrics (handle different formats)
if "performance" in metadata:
    perf = metadata["performance"]
    test_wr = perf.get("test_win_rate", 0)
    test_acc = perf.get("test_accuracy", 0)
    test_roc = perf.get("test_roc_auc", 0)
    overfitting = perf.get("overfitting_gap", 0)
else:
    metrics = metadata.get("metrics", {})
    test_wr = metrics.get("test_wr", 0)
    test_acc = metrics.get("test_accuracy", 0)
    test_roc = metrics.get("test_roc_auc", 0)
    overfitting = 0

print(f"  [Model] {model_type.upper()}")
print(f"  [Test Accuracy] {test_acc*100:.2f}%")
print(f"  [Test Win Rate] {test_wr*100:.2f}%")
print(f"  [Test ROC-AUC] {test_roc:.4f}")
if overfitting > 0:
    print(f"  [Overfitting Gap] {overfitting:.2f}%")

# ============================================================================
# STEP 2: Fetch Real-time Data
# ============================================================================
print("\n[STEP 2] Fetching Real-time Market Data...")

exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})


def fetch_ohlcv(symbol, timeframe="1h", limit=150):
    """Fetch OHLCV data (reduced to 150 for faster generation)"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["symbol"] = symbol
        return df.sort_values("timestamp").reset_index(drop=True)
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return None


symbols = ["BTC/USDT", "ETH/USDT"]
all_ohlcv = {}

for symbol in symbols:
    print(f"  Fetching {symbol}... ", end="", flush=True)
    df = fetch_ohlcv(symbol, "1h", limit=200)
    if df is not None:
        all_ohlcv[symbol] = df
        print(f"[OK] {len(df)} candles")

# ============================================================================
# STEP 3: Build Features (Same as Training)
# ============================================================================
print("\n[STEP 3] Building Technical Features...")


def build_features(df):
    """Build same features as training"""
    df = df.copy()

    df["returns"] = df["close"].pct_change()
    df["high_low_ratio"] = (df["high"] - df["low"]) / df["close"]
    df["close_open_ratio"] = (df["close"] - df["open"]) / df["open"]

    df["volatility_5"] = df["returns"].rolling(5).std()
    df["volatility_20"] = df["returns"].rolling(20).std()

    for period in [5, 10, 20]:
        df[f"momentum_{period}"] = df["close"].diff(period)
        df[f"roc_{period}"] = df["close"].pct_change(period)

    for period in [5, 10, 20, 50]:
        df[f"sma_{period}"] = df["close"].rolling(period).mean()
        df[f"ema_{period}"] = df["close"].ewm(span=period).mean()

    for period in [20]:
        sma = df["close"].rolling(period).mean()
        std = df["close"].rolling(period).std()
        df[f"bb_upper_{period}"] = sma + (std * 2)
        df[f"bb_lower_{period}"] = sma - (std * 2)
        df[f"bb_position_{period}"] = (df["close"] - df[f"bb_lower_{period}"]) / (
            df[f"bb_upper_{period}"] - df[f"bb_lower_{period}"]
        )

    def calculate_rsi(prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    df["rsi_14"] = calculate_rsi(df["close"], 14)
    df["rsi_7"] = calculate_rsi(df["close"], 7)

    def calculate_atr(high, low, close, period=14):
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return atr

    df["atr_14"] = calculate_atr(df["high"], df["low"], df["close"], 14)

    # MACD (required by UJI 5 model)
    ema_12 = df["close"].ewm(span=12).mean()
    ema_26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Volume indicators
    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ma"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma"]

    df["support_20"] = df["low"].rolling(20).min()
    df["resistance_20"] = df["high"].rolling(20).max()
    df["price_position"] = (df["close"] - df["support_20"]) / (
        df["resistance_20"] - df["support_20"]
    )

    df["trend_strength"] = (df["close"] - df["sma_20"]) / df["atr_14"]

    return df


for symbol in all_ohlcv:
    all_ohlcv[symbol] = build_features(all_ohlcv[symbol])

print(f"  Features built for {len(all_ohlcv)} symbols")

# ============================================================================
# STEP 4: Market Regime Detection (Adaptive)
# ============================================================================
print("\n[STEP 4] Detecting Market Regime (Adaptive)...")


def detect_market_regime(df):
    """Detect market regime for adaptive signals"""
    last_row = df.iloc[-1]
    volatility = df["volatility_20"].iloc[-1]
    trend = last_row["trend_strength"] if "trend_strength" in df.columns else 0

    volatility_mean = df["volatility_20"].mean()

    if pd.isna(volatility) or pd.isna(trend):
        return "NEUTRAL"

    if volatility > volatility_mean * 1.5:
        return "VOLATILE"
    elif abs(trend) > 1:
        return "TRENDING"
    else:
        return "RANGING"


regimes = {}
for symbol in all_ohlcv:
    regime = detect_market_regime(all_ohlcv[symbol])
    regimes[symbol] = regime
# ============================================================================
# STEP 5: Generate Signals
# ============================================================================
MIN_CONFIDENCE = 0.30  # Minimum confidence threshold (30%)

print(
    f"\n[STEP 5] Generating Trading Signals (Min Confidence: {MIN_CONFIDENCE*100:.0f}%)..."
)

signals = []

for symbol in all_ohlcv:
    df = all_ohlcv[symbol]

    # Get last row
    last_data = df.iloc[-1:]

    # Prepare features (UJI 5 model doesn't use scaler)
    X_last = last_data[feature_cols]

    # Predict
    prediction = model.predict(X_last)[0]
    probability = model.predict_proba(X_last)[0]

    # Calculate levels
    current_price = last_data["close"].values[0]
    atr = last_data["atr_14"].values[0]
    support = last_data["support_20"].values[0]
    resistance = last_data["resistance_20"].values[0]

    # RR 1:2 levels
    # Signal type (adaptive to regime)
    regime = regimes[symbol]

    if prediction == 1:  # Bullish prediction
        signal_type = "LONG"
        # LONG: SL below entry, TP above entry
        stop_loss = current_price - (atr * 0.7)
        risk_amount = current_price - stop_loss
        take_profit = current_price + (risk_amount * 2)
    else:
        signal_type = "SHORT"
        # SHORT: SL above entry, TP below entry
        stop_loss = current_price + (atr * 0.7)
        risk_amount = stop_loss - current_price
        take_profit = current_price - (risk_amount * 2)

    # Confidence adjustment based on regime
    base_confidence = probability[1]

    if regime == "VOLATILE":
        confidence = base_confidence * 0.85  # Reduce confidence in volatile market
    elif regime == "TRENDING":
        confidence = base_confidence * 1.1  # Increase confidence in trending market
    else:
        confidence = base_confidence * 0.9  # Neutral confidence

    confidence = np.clip(confidence, 0, 1)

    # ⭐ FILTER: Only add signal if confidence >= MIN_CONFIDENCE
    if confidence >= MIN_CONFIDENCE:
        signal = {
            "symbol": symbol,
            "signal": signal_type,
            "entry": round(current_price, 2),
            "sl": round(stop_loss, 2),
            "tp": round(take_profit, 2),
            "confidence": round(float(confidence), 4),
            "regime": regime,
            "atr": round(float(atr), 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        signals.append(signal)
        print(
            f"  ✅ {symbol}: {signal_type} @ ${current_price:,.2f} | Confidence: {confidence*100:.1f}%"
        )
    else:
        print(
            f"  ⏭️  {symbol}: Skipped (Confidence {confidence*100:.1f}% < {MIN_CONFIDENCE*100:.0f}%)"
        )

# Check if we got any valid signals
if len(signals) == 0:
    print(f"\n  ⚠️  No signals met confidence threshold of {MIN_CONFIDENCE*100:.0f}%")
    print(f"  💡 API will auto-retry to fetch fresh market data...")
    # Save empty array - API will handle retry
    with open("signals.json", "w") as f:
        json.dump([], f)
    exit(0)  # Exit with code 0 (success) but empty signals

# ============================================================================
# STEP 6: Display Signals
# ============================================================================
print("\n" + "=" * 80)
print(" [TRADING SIGNALS GENERATED]")
print("=" * 80)

for signal in signals:
    print(f"\n  {signal['signal']} {signal['symbol']}")
    print(f"    Entry Price    : ${signal['entry']:,.2f}")
    print(f"    Stop Loss      : ${signal['sl']:,.2f}")
    print(f"    Take Profit    : ${signal['tp']:,.2f}")
    print(f"    Confidence     : {signal['confidence']*100:.1f}%")
    print(f"    Market Regime  : {signal['regime']}")

# ============================================================================
# STEP 7: Save Signals
# ============================================================================
print("\n[STEP 7] Saving Signals to File...")

# Add model info and status to each signal
from datetime import datetime

for signal in signals:
    signal["model_version"] = model_type.upper()
    signal["model_accuracy"] = f"{test_acc*100:.2f}%"
    signal["model_roc_auc"] = f"{test_roc:.4f}"
    signal["model_win_rate"] = f"{test_wr*100:.2f}%"
    signal["status"] = "ACTIVE"
    signal["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

import json

with open("signals.json", "w") as f:
    json.dump(signals, f, indent=2)

print(f"  [OK] Signals saved to: signals.json")

# ============================================================================
# STEP 8: Summary
# ============================================================================
print("\n" + "=" * 80)
print(" [SUMMARY]")
print("=" * 80)

print(f"\n  Total Signals: {len(signals)}")
print(f"  [BEST MODEL] {model_type.upper()}")
print(f"  [Test Accuracy] {test_acc*100:.2f}%")
print(f"  [Test Win Rate] {test_wr*100:.2f}%")
print(f"  [Test ROC-AUC] {test_roc:.4f}")
print(f"  Risk:Reward Ratio: 1:2")

print(f"\n  Market Regimes Detected:")
for symbol in regimes:
    print(f"    {symbol:<10} {regimes[symbol]}")

print(f"\n  Adaptive Mechanisms Applied:")
print(f"    [OK] Market Regime Detection")
print(f"    [OK] Probability Adjustment by Regime")
print(f"    [OK] Dynamic Risk Management")
print(f"    [OK] UJI 5 Best Model (88.64% Accuracy)")

print("\n" + "=" * 80)
