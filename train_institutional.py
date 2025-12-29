"""
Institutional-Grade Model Training
Advanced features for professional trading
- Multi-timeframe analysis
- Advanced technical indicators
- Market regime detection
- Volatility clustering
- Smart money indicators
"""

import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timedelta
import warnings
import pickle
import json
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# Configuration
SYMBOLS = ["BTC/USDC", "ETH/USDC"]
TIMEFRAME = "1h"
LOOKBACK_DAYS = 70  # 70 days - balance between speed & quality
TRAIN_TEST_SPLIT = 0.2

print("=" * 80)
print(" [INSTITUTIONAL MODEL] - Advanced Trading System Training")
print("=" * 80)

# Initialize exchange
exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "spot"}})


def fetch_data(symbol, days=LOOKBACK_DAYS):
    """Fetch historical data"""
    print(f"\n[DATA] Fetching {symbol}...")
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


def add_institutional_features(df):
    """Add institutional-grade technical indicators"""

    # Basic price features
    df["returns"] = df["close"].pct_change()
    df["log_returns"] = np.log(df["close"] / df["close"].shift(1))

    # === TREND INDICATORS ===
    # Multiple EMAs
    for period in [8, 21, 55, 89, 200]:
        df[f"ema_{period}"] = df["close"].ewm(span=period).mean()
        df[f"ema_{period}_slope"] = df[f"ema_{period}"].pct_change(5)

    # MACD with histogram
    df["ema_12"] = df["close"].ewm(span=12).mean()
    df["ema_26"] = df["close"].ewm(span=26).mean()
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]
    df["macd_histogram_slope"] = df["macd_histogram"].pct_change()

    # === MOMENTUM INDICATORS ===
    # RSI with multiple periods
    for period in [14, 21]:
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

    # Stochastic RSI
    rsi = df["rsi_14"]
    df["stoch_rsi"] = (rsi - rsi.rolling(14).min()) / (
        rsi.rolling(14).max() - rsi.rolling(14).min()
    )

    # ROC (Rate of Change)
    for period in [9, 21]:
        df[f"roc_{period}"] = (
            (df["close"] - df["close"].shift(period)) / df["close"].shift(period)
        ) * 100

    # === VOLATILITY INDICATORS ===
    # ATR (Average True Range)
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
    # Volume trends
    df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

    # On-Balance Volume
    df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=20).mean()

    # VWAP
    df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vwap_distance"] = (df["close"] - df["vwap"]) / df["vwap"]

    # === SMART MONEY INDICATORS ===
    # Money Flow Index
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    money_flow = typical_price * df["volume"]

    positive_flow = (
        money_flow.where(typical_price > typical_price.shift(1), 0).rolling(14).sum()
    )
    negative_flow = (
        money_flow.where(typical_price < typical_price.shift(1), 0).rolling(14).sum()
    )
    df["mfi"] = 100 - (100 / (1 + positive_flow / negative_flow))

    # Accumulation/Distribution Line
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (
        df["high"] - df["low"]
    )
    df["adl"] = (clv * df["volume"]).cumsum()
    df["adl_ema"] = df["adl"].ewm(span=20).mean()

    # === MARKET STRUCTURE ===
    # Higher highs, lower lows detection
    df["hh"] = df["high"].rolling(20).max()
    df["ll"] = df["low"].rolling(20).min()
    df["market_structure"] = np.where(
        df["close"] > df["hh"].shift(1),
        1,  # Bullish
        np.where(df["close"] < df["ll"].shift(1), -1, 0),  # Bearish
    )

    # Pivot points
    df["pivot"] = (df["high"] + df["low"] + df["close"]) / 3
    df["r1"] = 2 * df["pivot"] - df["low"]
    df["s1"] = 2 * df["pivot"] - df["high"]

    # === REGIME DETECTION ===
    # Volatility regime
    df["volatility_regime"] = pd.qcut(
        df["atr_pct"], q=3, labels=["low", "medium", "high"]
    )
    df["vol_regime_numeric"] = df["volatility_regime"].map(
        {"low": 0, "medium": 1, "high": 2}
    )

    # Trend strength (ADX)
    plus_dm = df["high"].diff()
    minus_dm = -df["low"].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0

    tr_14 = df["tr"].rolling(14).sum()
    plus_di = 100 * (plus_dm.rolling(14).sum() / tr_14)
    minus_di = 100 * (minus_dm.rolling(14).sum() / tr_14)

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    df["adx"] = dx.rolling(14).mean()

    # === TIME-BASED FEATURES ===
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_asian_session"] = ((df["hour"] >= 0) & (df["hour"] < 8)).astype(int)
    df["is_london_session"] = ((df["hour"] >= 8) & (df["hour"] < 16)).astype(int)
    df["is_ny_session"] = ((df["hour"] >= 13) & (df["hour"] < 21)).astype(int)

    return df


def create_target(df, forward_periods=6):
    """Create target variable (future returns)"""
    df["future_return"] = (
        df["close"].shift(-forward_periods).pct_change(forward_periods)
    )

    # Classification: 1 = Buy (>0.5%), -1 = Sell (<-0.5%), 0 = Hold
    threshold = 0.005  # 0.5%
    df["target"] = 0
    df.loc[df["future_return"] > threshold, "target"] = 1
    df.loc[df["future_return"] < -threshold, "target"] = -1

    return df


def train_model(symbol_data_dict):
    """Train institutional-grade model"""
    print("\n[TRAINING] Building institutional model...")

    # Combine all symbols
    all_data = []
    for symbol, df in symbol_data_dict.items():
        df["symbol"] = symbol
        all_data.append(df)

    combined_df = pd.concat(all_data, ignore_index=True)

    # Remove NaN and infinite values
    combined_df = combined_df.replace([np.inf, -np.inf], np.nan)
    combined_df = combined_df.dropna()

    # Feature selection (exclude non-feature columns)
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
        "volatility_regime",
    ]
    feature_cols = [col for col in combined_df.columns if col not in exclude_cols]

    X = combined_df[feature_cols]
    y = combined_df["target"]

    # Convert to binary classification (1 = trade, 0 = no trade)
    y_binary = (y != 0).astype(int)

    print(f"  Features: {len(feature_cols)}")
    print(f"  Samples: {len(X)}")
    print(f"  Signal distribution: {y.value_counts().to_dict()}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y_binary, test_size=TRAIN_TEST_SPLIT, random_state=42, stratify=y_binary
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Advanced LightGBM with STRONG regularization (anti-overfitting)
    print("\n[MODEL] Training LightGBM with STRONG regularization...")

    param_grid = {
        "n_estimators": [200, 300],  # Fewer trees = less overfitting
        "max_depth": [4, 6, 8],  # Shallower trees = less overfitting
        "learning_rate": [0.01, 0.03],  # Lower LR = smoother learning
        "num_leaves": [15, 31],  # Less complexity = less overfitting
        "min_child_samples": [50, 100, 150],  # Higher = more generalization
        "subsample": [0.6, 0.7, 0.8],  # Row sampling = reduce overfitting
        "colsample_bytree": [0.6, 0.7],  # Column sampling = reduce overfitting
        "reg_alpha": [1.0, 2.0, 5.0],  # STRONG L1 regularization
        "reg_lambda": [1.0, 2.0, 5.0],  # STRONG L2 regularization
    }

    # Model with STRONG anti-overfitting settings
    model = LGBMClassifier(
        random_state=42,
        verbose=-1,
        class_weight="balanced",  # Handle imbalance
        min_split_gain=0.2,  # Higher gain requirement = less splits
        min_child_weight=0.01,  # Regularization
        max_bin=200,  # Reduce bins = less overfitting
    )

    grid_search = GridSearchCV(
        model,
        param_grid,
        cv=5,
        scoring="roc_auc",
        n_jobs=-1,
        verbose=1,
        return_train_score=True,  # Track train vs test
    )

    print("  Grid search running (this may take 10-20 minutes)...")
    grid_search.fit(X_train_scaled, y_train)

    best_model = grid_search.best_estimator_

    # Evaluate
    y_pred_train = best_model.predict(X_train_scaled)
    y_pred_test = best_model.predict(X_test_scaled)
    y_pred_proba = best_model.predict_proba(X_test_scaled)[:, 1]

    train_acc = accuracy_score(y_train, y_pred_train)
    test_acc = accuracy_score(y_test, y_pred_test)
    roc_auc = roc_auc_score(y_test, y_pred_proba)

    # Check overfitting
    overfitting_gap = train_acc - test_acc
    print(f"\n[RESULTS]")
    print(f"  Train Accuracy: {train_acc*100:.2f}%")
    print(f"  Test Accuracy: {test_acc*100:.2f}%")
    print(
        f"  Overfitting Gap: {overfitting_gap*100:.2f}% {'✅ Good' if overfitting_gap < 0.15 else '⚠️ High'}"
    )
    print(f"  ROC-AUC: {roc_auc:.4f}")
    print(f"  Best params: {grid_search.best_params_}")

    # Feature importance
    feature_importance = pd.DataFrame(
        {"feature": feature_cols, "importance": best_model.feature_importances_}
    ).sort_values("importance", ascending=False)

    print(f"\n[TOP FEATURES]")
    print(feature_importance.head(15).to_string(index=False))

    # Save model
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_filename = f"models/institutional_model_usdc_{timestamp}.pkl"

    model_data = {
        "model": best_model,
        "scaler": scaler,
        "feature_cols": feature_cols,
        "train_acc": train_acc,
        "test_acc": test_acc,
        "roc_auc": roc_auc,
        "symbols": SYMBOLS,
        "timestamp": timestamp,
    }

    with open(model_filename, "wb") as f:
        pickle.dump(model_data, f)

    # Save metadata
    metadata = {
        "timestamp": timestamp,
        "symbols": SYMBOLS,
        "train_accuracy": float(train_acc),
        "test_accuracy": float(test_acc),
        "roc_auc": float(roc_auc),
        "features_count": len(feature_cols),
        "best_params": grid_search.best_params_,
    }

    with open(f"models/institutional_metadata_{timestamp}.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[SAVED] Model: {model_filename}")

    return best_model, scaler, feature_cols, metadata


# Main execution
if __name__ == "__main__":
    print("\n[STEP 1] Fetching market data...")

    symbol_data = {}
    for symbol in SYMBOLS:
        df = fetch_data(symbol)
        df = add_institutional_features(df)
        df = create_target(df)
        symbol_data[symbol] = df
        print(f"  ✓ {symbol}: {len(df)} samples prepared")

    print("\n[STEP 2] Training institutional model...")
    model, scaler, features, metadata = train_model(symbol_data)

    print("\n" + "=" * 80)
    print(" [COMPLETE] Institutional model training finished!")
    print("=" * 80)
    print(f"\n📊 Model Performance:")
    print(f"  • Test Accuracy: {metadata['test_accuracy']*100:.2f}%")
    print(f"  • ROC-AUC: {metadata['roc_auc']:.4f}")
    print(f"  • Features: {metadata['features_count']}")
    print(f"\n🎯 Ready for 24/7 production trading!")
