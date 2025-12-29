"""
UJI 5 - FAST GridSearch untuk LightGBM Trading Model
Target: Cari parameter optimal dalam waktu <15 menit
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import json
import pickle
from pathlib import Path

warnings.filterwarnings("ignore")

import sys

sys.path.append(str(Path(__file__).parent))

import lightgbm as lgb
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
)

print("=" * 80)
print("🚀 UJI 5 - FAST GridSearch Training")
print("=" * 80)


# ==================== DATA LOADING ====================
def fetch_ohlcv(exchange, symbol, timeframe="1h", limit=1000):
    """Fetch OHLCV data from exchange"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        print(f"   Fetching {symbol}... ✓ {len(df)} candles")
        return df
    except Exception as e:
        print(f"   ❌ Error fetching {symbol}: {str(e)}")
        return None


def load_historical_data():
    """Load historical data for model training"""
    print("\n📂 Loading historical data...")

    exchange = ccxt.binance(
        {"enableRateLimit": True, "options": {"defaultType": "future"}}
    )

    symbols = ["BTC/USDT", "ETH/USDT"]
    all_data = []

    for symbol in symbols:
        df = fetch_ohlcv(exchange, symbol, timeframe="1h", limit=1000)
        if df is not None:
            df["symbol"] = symbol
            all_data.append(df)

    if not all_data:
        raise ValueError("No data fetched!")

    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"✅ Total data points: {len(combined_df)}")
    return combined_df


# ==================== FEATURE ENGINEERING ====================
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
    for period in [14]:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()
        rs = gain / loss
        df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # ATR
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift())
    low_close = abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()

    # Volume features
    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

    return df


def prepare_features(df):
    """Prepare features for training"""
    print("\n⚙️ Preparing features...")

    # Add technical indicators
    df_features = build_features(df)

    # Create labels (1 = BUY, -1 = SELL, 0 = HOLD)
    df_features["future_return"] = (
        df_features.groupby("symbol")["close"].shift(-5) / df_features["close"] - 1
    )

    # Signal logic: strong trends
    df_features["signal"] = 0
    df_features.loc[df_features["future_return"] > 0.015, "signal"] = (
        1  # BUY if >1.5% gain
    )
    df_features.loc[df_features["future_return"] < -0.015, "signal"] = (
        -1
    )  # SELL if <-1.5% loss

    # Drop rows with NaN
    df_features = df_features.dropna()

    # Filter only actionable signals (LONG or SHORT)
    df_features = df_features[df_features["signal"] != 0].copy()

    # Convert -1 (SHORT) to 0 for binary classification
    df_features["label"] = df_features["signal"].apply(lambda x: 1 if x == 1 else 0)

    print(f"   Total samples: {len(df_features)}")
    print(f"   LONG signals: {(df_features['label'] == 1).sum()}")
    print(f"   SHORT signals: {(df_features['label'] == 0).sum()}")

    return df_features


# ==================== MODEL TRAINING ====================
def train_fast_gridsearch_model(df_features):
    """
    Train LightGBM model dengan FAST GridSearch (reduced combinations)
    """
    print("\n🎯 Training LightGBM with FAST GridSearch...")

    # Select features
    feature_columns = [
        col
        for col in df_features.columns
        if col not in ["timestamp", "symbol", "future_return", "signal", "label"]
    ]

    X = df_features[feature_columns].values
    y = df_features["label"].values

    # Split: 60% train, 20% val, 20% test
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )

    print(f"\n📊 Data Split:")
    print(f"   Train: {len(X_train)} samples")
    print(f"   Val:   {len(X_val)} samples")
    print(f"   Test:  {len(X_test)} samples")

    # ========== FAST GridSearch - ONLY 54 combinations ==========
    print("\n🔍 FAST GridSearch Configuration:")
    print("   Parameter combinations: 54 (vs 13,122)")
    print("   Estimated time: ~5-10 minutes")

    param_grid = {
        # Focus on most impactful parameters
        "n_estimators": [500],  # Original best
        "learning_rate": [0.1],  # Original best
        "max_depth": [9, 10, 11],  # Slight variation
        "num_leaves": [31],  # Original best
        "min_child_samples": [10],  # Original best
        "subsample": [1.0],  # Original best
        "colsample_bytree": [1.0],  # Original best
        # Focus on regularization only (key for overfitting)
        "reg_alpha": [0.0, 0.01, 0.03],  # L1: 0 to minimal
        "reg_lambda": [0.0, 0.01, 0.03, 0.05, 0.1, 0.2],  # L2: 0 to light
    }

    print("\n📋 Parameter Grid:")
    for param, values in param_grid.items():
        print(f"   {param}: {values}")

    # Total combinations: 3 × 3 × 6 = 54
    total_combinations = 1
    for values in param_grid.values():
        total_combinations *= len(values)
    print(f"\n✅ Total combinations: {total_combinations}")

    # Combine train and val for GridSearch
    X_train_val = np.vstack([X_train, X_val])
    y_train_val = np.hstack([y_train, y_val])

    # Initialize LightGBM
    lgb_clf = lgb.LGBMClassifier(
        objective="binary", metric="auc", verbosity=-1, n_jobs=-1, random_state=42
    )

    # GridSearchCV with 3-fold CV
    grid_search = GridSearchCV(
        estimator=lgb_clf,
        param_grid=param_grid,
        cv=3,
        scoring="roc_auc",
        n_jobs=-1,
        verbose=2,
        return_train_score=True,
    )

    print("\n🔄 Starting GridSearch (this may take 5-10 minutes)...")
    print("   Please wait...\n")

    # Fit GridSearch
    grid_search.fit(X_train_val, y_train_val)

    print("\n✅ GridSearch Completed!")
    print(f"🏆 Best Cross-Validation ROC-AUC: {grid_search.best_score_:.4f}")
    print("\n📊 Best Hyperparameters Found:")
    for param, value in grid_search.best_params_.items():
        print(f"   {param}: {value}")

    # Get best model and retrain on train+val
    best_params = grid_search.best_params_
    best_params.update(
        {
            "objective": "binary",
            "metric": "auc",
            "verbosity": -1,
            "n_jobs": -1,
            "random_state": 42,
        }
    )

    print("\n🔄 Retraining with best parameters on full train+val set...")
    final_model = lgb.LGBMClassifier(**best_params)
    final_model.fit(X_train_val, y_train_val)

    # ========== EVALUATION ==========
    print("\n📊 Model Performance:")

    # Train set
    y_train_pred = final_model.predict(X_train)
    train_acc = accuracy_score(y_train, y_train_pred)
    train_wr = calculate_win_rate(y_train, y_train_pred)
    print(f"   Train - Accuracy: {train_acc*100:.2f}% | WR: {train_wr*100:.2f}%")

    # Val set
    y_val_pred = final_model.predict(X_val)
    val_acc = accuracy_score(y_val, y_val_pred)
    val_wr = calculate_win_rate(y_val, y_val_pred)
    print(f"   Val   - Accuracy: {val_acc*100:.2f}% | WR: {val_wr*100:.2f}%")

    # Test set (most important)
    y_test_pred = final_model.predict(X_test)
    y_test_proba = final_model.predict_proba(X_test)[:, 1]

    test_acc = accuracy_score(y_test, y_test_pred)
    test_wr = calculate_win_rate(y_test, y_test_pred)
    test_roc_auc = roc_auc_score(y_test, y_test_proba)

    print(
        f"   Test  - Accuracy: {test_acc*100:.2f}% | WR: {test_wr*100:.2f}% | ROC-AUC: {test_roc_auc:.4f}"
    )

    # Overfitting analysis
    print("\n🔍 Overfitting Analysis:")
    overfitting_gap = (train_acc - test_acc) * 100
    print(f"   Train-Test Gap: {overfitting_gap:.2f}%")

    if overfitting_gap > 20:
        print("   Status: ❌ Severe Overfitting Detected")
    elif overfitting_gap > 15:
        print("   Status: ⚠️  Moderate Overfitting")
    elif overfitting_gap > 10:
        print("   Status: ✅ Mild Overfitting (acceptable)")
    else:
        print("   Status: ✅ Well Generalized")

    # Detailed classification report
    print("\n📋 Detailed Classification Report (Test Set):")
    print(
        classification_report(
            y_test, y_test_pred, target_names=["SHORT", "LONG"], digits=4
        )
    )

    # Confusion matrix
    cm = confusion_matrix(y_test, y_test_pred)
    print("\n🎯 Confusion Matrix (Test Set):")
    print(f"                 Predicted")
    print(f"               SHORT  LONG")
    print(f"   Actual SHORT  {cm[0,0]:3d}   {cm[0,1]:3d}")
    print(f"          LONG   {cm[1,0]:3d}   {cm[1,1]:3d}")

    # Store metrics
    metrics = {
        "train_accuracy": float(train_acc),
        "val_accuracy": float(val_acc),
        "test_accuracy": float(test_acc),
        "train_win_rate": float(train_wr),
        "val_win_rate": float(val_wr),
        "test_win_rate": float(test_wr),
        "test_roc_auc": float(test_roc_auc),
        "overfitting_gap": float(overfitting_gap),
        "confusion_matrix": cm.tolist(),
        "best_cv_score": float(grid_search.best_score_),
        "best_params": best_params,
    }

    return final_model, best_params, metrics, feature_columns


def calculate_win_rate(y_true, y_pred):
    """Calculate Win Rate for trading signals"""
    correct = (y_true == y_pred).sum()
    total = len(y_true)
    return correct / total if total > 0 else 0


# ==================== MODEL COMPARISON ====================
def compare_with_previous_best():
    """Compare UJI 5 with previous best model"""
    print("\n" + "=" * 80)
    print("🔄 Comparing with Previous Best Model")
    print("=" * 80)

    # Load previous best model metadata
    models_dir = Path(__file__).parent / "models"
    prev_metadata_path = models_dir / "metadata_v2_lgb_20251220_171913.json"

    if not prev_metadata_path.exists():
        print("⚠️  Previous model metadata not found. Cannot compare.")
        return False

    with open(prev_metadata_path, "r") as f:
        prev_metadata = json.load(f)

    # Load current model metadata
    curr_metadata_files = sorted(models_dir.glob("metadata_v2_lgb_uji5_*.json"))
    if not curr_metadata_files:
        print("❌ Current model metadata not found!")
        return False

    with open(curr_metadata_files[-1], "r") as f:
        curr_metadata = json.load(f)

    # Extract metrics
    prev_acc = prev_metadata["performance"]["test_accuracy"] * 100
    prev_wr = prev_metadata["performance"]["test_win_rate"] * 100
    prev_roc = prev_metadata["performance"]["test_roc_auc"]
    prev_overfitting = prev_metadata["performance"]["overfitting_gap"]

    curr_acc = curr_metadata["performance"]["test_accuracy"] * 100
    curr_wr = curr_metadata["performance"]["test_win_rate"] * 100
    curr_roc = curr_metadata["performance"]["test_roc_auc"]
    curr_overfitting = curr_metadata["performance"]["overfitting_gap"]

    # Print comparison
    print(
        "\nMetric               Previous             Current (UJI 5)      Improvement"
    )
    print("-" * 80)

    # Accuracy
    acc_diff = curr_acc - prev_acc
    acc_status = "✅" if acc_diff >= 0 else "❌"
    print(
        f"Test Accuracy        {prev_acc:6.2f}%              {curr_acc:6.2f}%              {acc_status} {acc_diff:+.2f}%"
    )

    # Win Rate
    wr_diff = curr_wr - prev_wr
    wr_status = "✅" if wr_diff >= 0 else "❌"
    print(
        f"Test Win Rate        {prev_wr:6.2f}%              {curr_wr:6.2f}%              {wr_status} {wr_diff:+.2f}%"
    )

    # ROC-AUC
    roc_diff = curr_roc - prev_roc
    roc_status = "✅" if roc_diff >= 0 else "❌"
    print(
        f"Test ROC-AUC        {prev_roc:7.4f}              {curr_roc:7.4f}               {roc_status} {roc_diff:+.4f}"
    )

    # Overfitting
    overfitting_diff = prev_overfitting - curr_overfitting  # Lower is better
    overfitting_status = "✅" if overfitting_diff >= 0 else "❌"
    print(
        f"Overfitting Gap     {prev_overfitting:6.2f}%               {curr_overfitting:6.2f}%              {overfitting_status}"
    )

    # Decision logic - LENIENT (must beat on at least 2/4 metrics)
    score = 0
    if acc_diff >= 0:
        score += 1  # Accuracy improved or same
    if wr_diff >= 0:
        score += 1  # WR improved or same
    if roc_diff >= 0:
        score += 1  # ROC-AUC improved or same
    if overfitting_diff > 0:
        score += 1  # Overfitting reduced

    print("\n" + "=" * 80)
    if score >= 2:
        print("✅ DECISION: Model UJI 5 LEBIH BAIK atau SETARA")
        print(f"   Score: {score}/4 metrics improved")
        print("   💾 Model UJI 5 akan digunakan untuk production!")
        return True
    else:
        print("❌ DECISION: Model UJI 5 TIDAK LEBIH BAIK - Tetap pakai model lama")
        print(f"   Score: {score}/4 metrics improved")
        print("   ⚠️  Model UJI 5 disimpan untuk referensi, tapi TIDAK akan dipakai.")
        return False


# ==================== SAVE MODEL ====================
def save_model(model, metadata, feature_columns):
    """Save trained model and metadata"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_name = f"best_model_v2_lgb_uji5_{timestamp}.pkl"
    metadata_name = f"metadata_v2_lgb_uji5_{timestamp}.json"
    features_name = f"features_v2_lgb_uji5_{timestamp}.json"

    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)

    # Save model
    model_path = models_dir / model_name
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    # Save metadata
    metadata_path = models_dir / metadata_name
    metadata["model_file"] = model_name
    metadata["features_file"] = features_name
    metadata["training_date"] = timestamp
    metadata["model_version"] = "v2_lgb_uji5"

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    # Save feature columns
    features_path = models_dir / features_name
    with open(features_path, "w") as f:
        json.dump({"feature_columns": feature_columns}, f, indent=4)

    print(f"\n💾 Saving model: v2_lgb_uji5_{timestamp}")
    print(f"   Model: {model_path}")
    print(f"   Metadata: {metadata_path}")
    print(f"   Features: {features_path}")


# ==================== MAIN ====================
def main():
    """Main training pipeline"""
    try:
        # Load data
        df_raw = load_historical_data()

        # Prepare features
        df_features = prepare_features(df_raw)

        # Train model with FAST GridSearch
        model, best_params, metrics, feature_columns = train_fast_gridsearch_model(
            df_features
        )

        # Save model
        metadata = {
            "performance": metrics,
            "hyperparameters": best_params,
            "training_samples": len(df_features),
            "features_count": len(feature_columns),
        }
        save_model(model, metadata, feature_columns)

        # Compare with previous best
        is_better = compare_with_previous_best()

        print("\n" + "=" * 80)
        print("✅ UJI 5 FAST GridSearch Training Completed!")
        print("=" * 80)

        if is_better:
            print("\n🎉 Model baru BERHASIL! Silakan update signal_generator_v2.py")
        else:
            print("\n⚠️  Model baru TIDAK lebih baik. Tetap gunakan model lama.")

    except Exception as e:
        print(f"\n❌ Error during training: {str(e)}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
