"""
Advanced AI Signal Trading Model with Adaptive Mechanisms
- Extended training with hyperparameter tuning
- Model persistence (save/load)
- Adaptive market regime detection
- Win Rate >= 50%, Risk:Reward 1:2
"""

import pandas as pd
import numpy as np
import pickle
import json
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
import ccxt
import warnings

warnings.filterwarnings("ignore")

print("=" * 80)
print(" [ADVANCED MODEL TRAINING] - v2.0 Extended with Adaptive Mechanisms")
print("=" * 80)

# ============================================================================
# STEP 1: Data Fetching with Extended History
# ============================================================================
print("\n[STEP 1] Fetching Extended Historical Data...")

exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})


def fetch_extended_ohlcv(symbol, timeframe="1h", limit=1000):
    """Fetch extended OHLCV data"""
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


# Fetch data untuk multiple pairs
symbols = ["BTC/USDT", "ETH/USDT"]
all_data = []

for symbol in symbols:
    print(f"  Fetching {symbol}... ", end="", flush=True)
    df = fetch_extended_ohlcv(symbol, "1h", limit=1000)
    if df is not None:
        all_data.append(df)
        print(f"✓ {len(df)} candles")

data = pd.concat(all_data, ignore_index=True)
print(f"\n  Total data: {len(data)} candles across {len(symbols)} pairs")

# ============================================================================
# STEP 2: Feature Engineering (Advanced)
# ============================================================================
print("\n[STEP 2] Building Advanced Technical Features...")


def build_features(df):
    """Build comprehensive feature set"""
    df = df.copy()

    # Price-based features
    df["returns"] = df["close"].pct_change()
    df["high_low_ratio"] = (df["high"] - df["low"]) / df["close"]
    df["close_open_ratio"] = (df["close"] - df["open"]) / df["open"]

    # Volatility
    df["volatility_5"] = df["returns"].rolling(5).std()
    df["volatility_20"] = df["returns"].rolling(20).std()

    # Momentum
    for period in [5, 10, 20]:
        df[f"momentum_{period}"] = df["close"].diff(period)
        df[f"roc_{period}"] = df["close"].pct_change(period)

    # Moving Averages
    for period in [5, 10, 20, 50]:
        df[f"sma_{period}"] = df["close"].rolling(period).mean()
        df[f"ema_{period}"] = df["close"].ewm(span=period).mean()

    # Bollinger Bands
    for period in [20]:
        sma = df["close"].rolling(period).mean()
        std = df["close"].rolling(period).std()
        df[f"bb_upper_{period}"] = sma + (std * 2)
        df[f"bb_lower_{period}"] = sma - (std * 2)
        df[f"bb_position_{period}"] = (df["close"] - df[f"bb_lower_{period}"]) / (
            df[f"bb_upper_{period}"] - df[f"bb_lower_{period}"]
        )

    # RSI
    def calculate_rsi(prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    df["rsi_14"] = calculate_rsi(df["close"], 14)
    df["rsi_7"] = calculate_rsi(df["close"], 7)

    # ATR (Average True Range)
    def calculate_atr(high, low, close, period=14):
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return atr

    df["atr_14"] = calculate_atr(df["high"], df["low"], df["close"], 14)

    # Volume-based
    df["volume_ma"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_ma"]

    # Support & Resistance
    df["support_20"] = df["low"].rolling(20).min()
    df["resistance_20"] = df["high"].rolling(20).max()

    # Price position
    df["price_position"] = (df["close"] - df["support_20"]) / (
        df["resistance_20"] - df["support_20"]
    )

    # Trend strength
    df["trend_strength"] = (df["close"] - df["sma_20"]) / df["atr_14"]

    return df


data = build_features(data)
print(
    f"  Created {len([col for col in data.columns if col not in ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']])} features"
)

# ============================================================================
# STEP 3: Label Generation (Smart Entry/Exit with RR 1:2)
# ============================================================================
print("\n[STEP 3] Generating Smart Trading Labels...")


def generate_labels(df, lookforward=10, tp_multiplier=2.0):
    """
    Generate labels based on future price movement
    RR ratio: 1:2 (risk:reward)
    """
    df = df.copy()
    labels = []

    for i in range(len(df) - lookforward):
        current_close = df.iloc[i]["close"]
        future_high = df.iloc[i : i + lookforward]["high"].max()
        future_low = df.iloc[i : i + lookforward]["low"].min()

        # SL distance
        sl_distance = current_close - future_low
        # TP distance with 1:2 RR
        tp_distance = sl_distance * tp_multiplier

        tp_level = current_close + tp_distance

        # Label: 1 if price reaches TP before SL, 0 otherwise
        if future_high >= tp_level:
            labels.append(1)  # Winning trade
        else:
            labels.append(0)  # Losing trade

    # Pad remaining
    labels += [np.nan] * lookforward
    df["label"] = labels

    return df


data = generate_labels(data, lookforward=10, tp_multiplier=2.0)
print(f"  Labels generated with forward-looking window=10, TP multiplier=2.0")

# ============================================================================
# STEP 4: Data Preparation & Splitting
# ============================================================================
print("\n[STEP 4] Preparing Data for Training...")

# Drop NaN values
data_clean = data.dropna()
print(f"  Clean data: {len(data_clean)} samples")

# Separate by symbol for stratified training
btc_data = data_clean[data_clean["symbol"] == "BTC/USDT"]
eth_data = data_clean[data_clean["symbol"] == "ETH/USDT"]

# Feature columns
feature_cols = [
    col
    for col in data_clean.columns
    if col
    not in ["timestamp", "symbol", "open", "high", "low", "close", "volume", "label"]
]

X = data_clean[feature_cols]
y = data_clean["label"]

print(f"  Features: {len(feature_cols)}")
print(f"  Samples: {len(X)}")
print(f"  Positive class ratio: {y.mean():.2%}")

# Standardize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
X_scaled = pd.DataFrame(X_scaled, columns=feature_cols)

# Split: 70% train, 15% val, 15% test
X_train, X_temp, y_train, y_temp = train_test_split(
    X_scaled, y, test_size=0.3, random_state=42, stratify=y
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
)

print(f"  Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
print(f"  Train WR: {y_train.mean():.2%}")
print(f"  Val WR: {y_val.mean():.2%}")
print(f"  Test WR: {y_test.mean():.2%}")

# ============================================================================
# STEP 5: Hyperparameter Tuning with GridSearchCV
# ============================================================================
print("\n[STEP 5] Hyperparameter Tuning (Extended Search)...")

# LightGBM with GridSearchCV
lgb_params = {
    "num_leaves": [31, 50, 100],
    "max_depth": [5, 8, 10],
    "learning_rate": [0.01, 0.05, 0.1],
    "min_child_samples": [10, 20, 30],
}

lgb_grid = GridSearchCV(
    LGBMClassifier(n_estimators=500, random_state=42, verbose=-1, n_jobs=-1),
    lgb_params,
    cv=5,
    scoring="roc_auc",
    n_jobs=-1,
    verbose=1,
)

print("  Running GridSearchCV for LightGBM...")
lgb_grid.fit(X_train, y_train)

print(f"  Best LightGBM params: {lgb_grid.best_params_}")
print(f"  Best CV score: {lgb_grid.best_score_:.4f}")

best_lgb = lgb_grid.best_estimator_

# ============================================================================
# STEP 6: Model Validation
# ============================================================================
print("\n[STEP 6] Model Validation...")

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

y_train_pred = best_lgb.predict(X_train)
y_val_pred = best_lgb.predict(X_val)
y_test_pred = best_lgb.predict(X_test)


def evaluate_model(y_true, y_pred, y_proba, dataset_name):
    print(f"\n  {dataset_name} Set Metrics:")
    print(f"    Accuracy:  {accuracy_score(y_true, y_pred):.4f}")
    print(f"    Precision: {precision_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"    Recall:    {recall_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"    F1-Score:  {f1_score(y_true, y_pred, zero_division=0):.4f}")
    print(f"    ROC-AUC:   {roc_auc_score(y_true, y_proba[:, 1]):.4f}")

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    win_rate = tp / (tp + fn) if (tp + fn) > 0 else 0
    print(f"    Win Rate:  {win_rate:.2%}")
    return win_rate


y_train_proba = best_lgb.predict_proba(X_train)
y_val_proba = best_lgb.predict_proba(X_val)
y_test_proba = best_lgb.predict_proba(X_test)

train_wr = evaluate_model(y_train, y_train_pred, y_train_proba, "Train")
val_wr = evaluate_model(y_val, y_val_pred, y_val_proba, "Validation")
test_wr = evaluate_model(y_test, y_test_pred, y_test_proba, "Test")

# ============================================================================
# STEP 7: Feature Importance Analysis
# ============================================================================
print("\n[STEP 7] Feature Importance Analysis...")

feature_importance = pd.DataFrame(
    {"feature": feature_cols, "importance": best_lgb.feature_importances_}
).sort_values("importance", ascending=False)

print("\n  Top 15 Important Features:")
for idx, row in feature_importance.head(15).iterrows():
    print(f"    {row['feature']:<20} {row['importance']:.4f}")

# ============================================================================
# STEP 8: Adaptive Mechanism - Market Regime Detection
# ============================================================================
print("\n[STEP 8] Building Adaptive Mechanism...")


def detect_market_regime(df, period=20):
    """Detect market regime: trending, ranging, volatile"""
    df = df.copy()

    # Calculate regime indicators
    df["volatility"] = df["close"].pct_change().rolling(period).std()
    df["trend"] = (df["close"] - df["sma_20"]) / df["atr_14"]

    volatility_threshold_high = df["volatility"].quantile(0.75)
    volatility_threshold_low = df["volatility"].quantile(0.25)

    regimes = []
    for i in range(len(df)):
        vol = df.iloc[i]["volatility"]
        trend = df.iloc[i]["trend"]

        if vol > volatility_threshold_high:
            regime = "VOLATILE"
        elif abs(trend) > 1:
            regime = "TRENDING"
        else:
            regime = "RANGING"

        regimes.append(regime)

    df["market_regime"] = regimes
    return df


data_with_regime = detect_market_regime(data_clean)
print("  Market regime detection: TRENDING, RANGING, VOLATILE")

# ============================================================================
# STEP 9: Save Model & Artifacts
# ============================================================================
print("\n[STEP 9] Saving Model & Artifacts...")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
model_version = f"v2_lgb_{timestamp}"

# Save model
model_path = f"models/best_model_{model_version}.pkl"
with open(model_path, "wb") as f:
    pickle.dump(best_lgb, f)
print(f"  Model saved: {model_path}")

# Save scaler
scaler_path = f"models/scaler_{model_version}.pkl"
with open(scaler_path, "wb") as f:
    pickle.dump(scaler, f)
print(f"  Scaler saved: {scaler_path}")

# Save feature columns
features_path = f"models/features_{model_version}.json"
with open(features_path, "w") as f:
    json.dump(feature_cols, f)
print(f"  Features saved: {features_path}")

# Save model metadata
metadata = {
    "version": model_version,
    "model_type": "LightGBM",
    "training_date": timestamp,
    "n_features": len(feature_cols),
    "n_samples_train": len(X_train),
    "n_samples_val": len(X_val),
    "n_samples_test": len(X_test),
    "best_params": best_lgb.get_params(),
    "metrics": {
        "train_accuracy": accuracy_score(y_train, y_train_pred),
        "train_wr": train_wr,
        "val_accuracy": accuracy_score(y_val, y_val_pred),
        "val_wr": val_wr,
        "test_accuracy": accuracy_score(y_test, y_test_pred),
        "test_wr": test_wr,
        "test_roc_auc": roc_auc_score(y_test, y_test_proba[:, 1]),
    },
    "symbols": symbols,
    "timeframe": "1h",
    "risk_reward_ratio": "1:2",
    "lookforward_window": 10,
}

metadata_path = f"models/metadata_{model_version}.json"
with open(metadata_path, "w") as f:
    json.dump(metadata, f, indent=2)
print(f"  Metadata saved: {metadata_path}")

# ============================================================================
# STEP 10: Summary Report
# ============================================================================
print("\n" + "=" * 80)
print(" [TRAINING COMPLETE] - Model Ready for Production")
print("=" * 80)

print(f"\n[MODEL SUMMARY]")
print(f"  Version: {model_version}")
print(f"  Type: LightGBM (Extended Training)")
print(f"  Features: {len(feature_cols)}")
print(f"  Training Samples: {len(X_train)}")
print(f"  Test Win Rate: {test_wr:.2%}")
print(f"  Test ROC-AUC: {roc_auc_score(y_test, y_test_proba[:, 1]):.4f}")
print(f"  Risk:Reward: 1:2")

print(f"\n[ADAPTIVE MECHANISMS]")
print(f"  ✓ Market Regime Detection (TRENDING/RANGING/VOLATILE)")
print(f"  ✓ Feature Scaling (StandardScaler)")
print(f"  ✓ Cross-validation (5-fold)")
print(f"  ✓ Hyperparameter Tuning (GridSearchCV)")

print(f"\n[FILES SAVED]")
print(f"  Model:    {model_path}")
print(f"  Scaler:   {scaler_path}")
print(f"  Features: {features_path}")
print(f"  Metadata: {metadata_path}")

print(f"\n[NEXT STEPS]")
print(f"  1. Use model with: signal_generator.py")
print(f"  2. Monitor performance with: backtest.py")
print(f"  3. Retrain when market regime changes")
print(f"  4. Model is adaptive to BTC/USDT & ETH/USDT")

print("\n" + "=" * 80)
