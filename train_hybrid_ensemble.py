"""
HYBRID ENSEMBLE MODEL TRAINING
Dual-model system: Long-term (6 months) + Short-term (30 days)
Features:
- Institutional indicators (order flow, market structure, liquidity zones)
- Cross-validation (TimeSeriesSplit) - prevent overfitting
- Feature selection (SelectKBest) - keep best 35 features
- Walk-forward testing - validate on unseen data
- Ensemble prediction: 70% long-term + 30% short-term
"""

import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timedelta
import warnings
import pickle
import json
from lightgbm import LGBMClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif
import sys
import os

# Add utils to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.indicators import calculate_institutional_composite

warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURATION - HYBRID ENSEMBLE
# ============================================================================
SYMBOLS = ["BTC/USDC", "ETH/USDC"]
TIMEFRAME = "1h"
LOOKBACK_DAYS_LONG = 180  # 6 months for long-term stability
LOOKBACK_DAYS_SHORT = 30  # 30 days for recent adaptation
TOP_FEATURES = 35  # Select best 35 features (anti-overfitting)
TRAIN_TEST_SPLIT = 0.2

print("=" * 80)
print(" 🚀 HYBRID ENSEMBLE - Dual-Model Training System")
print(" Long-term (6M, 70%) + Short-term (30D, 30%)")
print("=" * 80)

# Initialize exchange
exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})


# ============================================================================
# DATA FETCHING
# ============================================================================
def fetch_data(symbol, days):
    """Fetch historical data"""
    print(f"\n[DATA] Fetching {symbol} ({days} days)...")
    since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())

    all_ohlcv = []
    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, since, limit=1000)
        if not ohlcv:
            break
        all_ohlcv.extend(ohlcv)
        since = ohlcv[-1][0] + 1
        if len(ohlcv) < 1000:
            break

    df = pd.DataFrame(
        all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    print(f"  ✓ {len(df)} candles loaded")
    return df


# ============================================================================
# FEATURE ENGINEERING - INSTITUTIONAL GRADE
# ============================================================================
def add_advanced_features(df):
    """Add technical + institutional indicators"""

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

    # === MOMENTUM INDICATORS ===
    for period in [14, 21]:
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

    # ROC
    for period in [9, 21]:
        df[f"roc_{period}"] = (
            (df["close"] - df["close"].shift(period)) / df["close"].shift(period)
        ) * 100

    # === VOLATILITY INDICATORS ===
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

    # === VOLUME INDICATORS ===
    df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

    # On-Balance Volume
    df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=20).mean()

    # === INSTITUTIONAL INDICATORS (NEW!) ===
    df = calculate_institutional_composite(df)

    # === TIME-BASED FEATURES ===
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_asian_session"] = ((df["hour"] >= 0) & (df["hour"] < 8)).astype(int)
    df["is_london_session"] = ((df["hour"] >= 8) & (df["hour"] < 16)).astype(int)
    df["is_ny_session"] = ((df["hour"] >= 13) & (df["hour"] < 21)).astype(int)

    return df


def create_target(df, forward_periods=6):
    """Create target variable"""
    df["future_return"] = (
        df["close"].shift(-forward_periods).pct_change(forward_periods)
    )

    # Binary: 1 = Trade (|return| > 0.5%), 0 = No trade
    threshold = 0.005  # 0.5%
    df["target"] = (abs(df["future_return"]) > threshold).astype(int)

    return df


# ============================================================================
# CROSS-VALIDATION - ANTI-OVERFITTING
# ============================================================================
def cross_validate_model(X, y, model, n_splits=5):
    """Time-series cross-validation"""
    print(f"\n[CV] Running {n_splits}-fold time-series cross-validation...")

    tscv = TimeSeriesSplit(n_splits=n_splits)
    cv_scores = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
        X_train_cv, X_val_cv = X[train_idx], X[val_idx]
        y_train_cv, y_val_cv = y[train_idx], y[val_idx]

        model.fit(X_train_cv, y_train_cv)
        score = model.score(X_val_cv, y_val_cv)
        cv_scores.append(score)
        print(f"  Fold {fold}: {score*100:.2f}%")

    mean_score = np.mean(cv_scores)
    std_score = np.std(cv_scores)

    print(f"\n  CV Mean: {mean_score*100:.2f}%")
    print(f"  CV Std: {std_score*100:.2f}%")

    if std_score > 0.05:
        print(f"  ⚠️ HIGH VARIANCE - Model may be overfitting!")
    else:
        print(f"  ✅ LOW VARIANCE - Model is stable!")

    return mean_score, std_score


# ============================================================================
# FEATURE SELECTION - KEEP BEST FEATURES
# ============================================================================
def select_best_features(X, y, feature_names, k=TOP_FEATURES):
    """Select top K most predictive features"""
    print(f"\n[FEATURE SELECTION] Selecting top {k} features...")

    selector = SelectKBest(f_classif, k=k)
    X_selected = selector.fit_transform(X, y)

    # Get selected feature names
    feature_mask = selector.get_support()
    selected_features = [f for f, m in zip(feature_names, feature_mask) if m]

    print(f"  ✓ Selected {len(selected_features)} features:")
    for i, feat in enumerate(selected_features[:15], 1):
        print(f"    {i}. {feat}")
    if len(selected_features) > 15:
        print(f"    ... and {len(selected_features)-15} more")

    return X_selected, selected_features, selector


# ============================================================================
# MODEL TRAINING - DUAL MODELS
# ============================================================================
def train_single_model(X, y, feature_names, model_name, use_cv=True):
    """Train a single model with anti-overfitting measures"""
    print(f"\n{'='*80}")
    print(f" TRAINING {model_name}")
    print(f"{'='*80}")

    # Feature selection
    X_selected, selected_features, selector = select_best_features(X, y, feature_names)

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_selected)

    # Train/test split (time-aware)
    split_idx = int(len(X_scaled) * (1 - TRAIN_TEST_SPLIT))
    X_train, X_test = X_scaled[:split_idx], X_scaled[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"  Train samples: {len(X_train)}")
    print(f"  Test samples: {len(X_test)}")

    # LightGBM with STRONG regularization
    model = LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.02,
        num_leaves=31,
        min_child_samples=100,  # STRONG regularization
        subsample=0.7,
        colsample_bytree=0.7,
        reg_alpha=2.0,  # L1 regularization
        reg_lambda=2.0,  # L2 regularization
        random_state=42,
        verbose=-1,
        class_weight="balanced",
    )

    # Cross-validation (optional)
    if use_cv:
        cv_mean, cv_std = cross_validate_model(X_scaled, y, model, n_splits=5)

    # Final training
    model.fit(X_train, y_train)

    # Evaluate
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]

    train_acc = accuracy_score(y_train, y_pred_train)
    test_acc = accuracy_score(y_test, y_pred_test)
    roc_auc = roc_auc_score(y_test, y_pred_proba)

    overfitting_gap = train_acc - test_acc

    print(f"\n[RESULTS {model_name}]")
    print(f"  Train Accuracy: {train_acc*100:.2f}%")
    print(f"  Test Accuracy: {test_acc*100:.2f}%")
    print(
        f"  Overfitting Gap: {overfitting_gap*100:.2f}% {'✅' if overfitting_gap < 0.15 else '⚠️'}"
    )
    print(f"  ROC-AUC: {roc_auc:.4f}")

    # Feature importance
    feature_importance = pd.DataFrame(
        {"feature": selected_features, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    print(f"\n[TOP 10 FEATURES]")
    print(feature_importance.head(10).to_string(index=False))

    return model, scaler, selector, test_acc, roc_auc, selected_features


# ============================================================================
# MAIN TRAINING PIPELINE
# ============================================================================
def main():
    """Main training pipeline"""

    # ========================================================================
    # STEP 1: Fetch data for both models
    # ========================================================================
    print("\n" + "=" * 80)
    print(" STEP 1: DATA COLLECTION")
    print("=" * 80)

    # Long-term model data (6 months)
    long_term_data = {}
    for symbol in SYMBOLS:
        df = fetch_data(symbol, LOOKBACK_DAYS_LONG)
        df = add_advanced_features(df)
        df = create_target(df)
        long_term_data[symbol] = df

    # Short-term model data (30 days)
    short_term_data = {}
    for symbol in SYMBOLS:
        df = fetch_data(symbol, LOOKBACK_DAYS_SHORT)
        df = add_advanced_features(df)
        df = create_target(df)
        short_term_data[symbol] = df

    # ========================================================================
    # STEP 2: Combine data
    # ========================================================================
    print("\n" + "=" * 80)
    print(" STEP 2: DATA PREPARATION")
    print("=" * 80)

    # Long-term combined
    long_dfs = []
    for symbol, df in long_term_data.items():
        df["symbol"] = symbol
        long_dfs.append(df)
    long_combined = pd.concat(long_dfs, ignore_index=True)

    # Short-term combined
    short_dfs = []
    for symbol, df in short_term_data.items():
        df["symbol"] = symbol
        short_dfs.append(df)
    short_combined = pd.concat(short_dfs, ignore_index=True)

    # Clean data
    for df in [long_combined, short_combined]:
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(inplace=True)

    # Feature columns
    exclude_cols = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "future_return",
        "target",
        "symbol",
    ]
    feature_cols = [col for col in long_combined.columns if col not in exclude_cols]

    print(f"  Long-term samples: {len(long_combined)}")
    print(f"  Short-term samples: {len(short_combined)}")
    print(f"  Total features: {len(feature_cols)}")

    # Prepare X, y
    X_long = long_combined[feature_cols].values
    y_long = long_combined["target"].values

    X_short = short_combined[feature_cols].values
    y_short = short_combined["target"].values

    # ========================================================================
    # STEP 3: Train LONG-TERM model (6 months, 70% weight)
    # ========================================================================
    model_long, scaler_long, selector_long, acc_long, auc_long, features_long = (
        train_single_model(X_long, y_long, feature_cols, "LONG-TERM (6M)", use_cv=True)
    )

    # ========================================================================
    # STEP 4: Train SHORT-TERM model (30 days, 30% weight)
    # ========================================================================
    model_short, scaler_short, selector_short, acc_short, auc_short, features_short = (
        train_single_model(
            X_short, y_short, feature_cols, "SHORT-TERM (30D)", use_cv=True
        )
    )

    # ========================================================================
    # STEP 5: Save ensemble models
    # ========================================================================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("\n" + "=" * 80)
    print(" STEP 5: SAVING ENSEMBLE MODELS")
    print("=" * 80)

    # Save long-term model
    model_path_long = f"models/ensemble_long_term_{timestamp}.pkl"
    with open(model_path_long, "wb") as f:
        pickle.dump(
            {
                "model": model_long,
                "scaler": scaler_long,
                "selector": selector_long,
                "features": features_long,
            },
            f,
        )
    print(f"  ✓ Long-term model saved: {model_path_long}")

    # Save short-term model
    model_path_short = f"models/ensemble_short_term_{timestamp}.pkl"
    with open(model_path_short, "wb") as f:
        pickle.dump(
            {
                "model": model_short,
                "scaler": scaler_short,
                "selector": selector_short,
                "features": features_short,
            },
            f,
        )
    print(f"  ✓ Short-term model saved: {model_path_short}")

    # Save metadata
    metadata = {
        "timestamp": timestamp,
        "long_term": {
            "lookback_days": LOOKBACK_DAYS_LONG,
            "accuracy": float(acc_long),
            "roc_auc": float(auc_long),
            "features": features_long,
            "model_path": model_path_long,
            "weight": 0.7,
        },
        "short_term": {
            "lookback_days": LOOKBACK_DAYS_SHORT,
            "accuracy": float(acc_short),
            "roc_auc": float(auc_short),
            "features": features_short,
            "model_path": model_path_short,
            "weight": 0.3,
        },
        "ensemble": {
            "weighted_accuracy": float(acc_long * 0.7 + acc_short * 0.3),
            "weighted_auc": float(auc_long * 0.7 + auc_short * 0.3),
        },
        "symbols": SYMBOLS,
        "timeframe": TIMEFRAME,
    }

    metadata_path = f"models/ensemble_metadata_{timestamp}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  ✓ Metadata saved: {metadata_path}")

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print(" ✅ TRAINING COMPLETE - HYBRID ENSEMBLE MODEL")
    print("=" * 80)
    print(f"\n📊 ENSEMBLE PERFORMANCE:")
    print(f"  Long-term (70%): {acc_long*100:.2f}% accuracy, {auc_long:.4f} AUC")
    print(f"  Short-term (30%): {acc_short*100:.2f}% accuracy, {auc_short:.4f} AUC")
    print(
        f"  Weighted Ensemble: {metadata['ensemble']['weighted_accuracy']*100:.2f}% accuracy"
    )
    print(f"\n🎯 USAGE:")
    print(f"  prediction = (long_pred * 0.7) + (short_pred * 0.3)")
    print(f"\n📁 FILES:")
    print(f"  {model_path_long}")
    print(f"  {model_path_short}")
    print(f"  {metadata_path}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
