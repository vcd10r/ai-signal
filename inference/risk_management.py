"""
Risk management utilities for trading signals
"""


def generate_signal_with_levels(
    df_features=None,
    signal_type="LONG",
    entry_price=None,
    probability=None,
    atr_multiplier_sl=1.5,
    atr_multiplier_tp=3.0,
    min_rr_ratio=2.0,
    **kwargs
):
    """
    Generate signal with SL and TP based on entry and ATR

    Args:
        df_features: DataFrame with technical indicators
        signal_type: "LONG" or "SHORT"
        entry_price: Entry price
        probability: Signal confidence
        atr_multiplier_sl: ATR multiplier for stop loss
        atr_multiplier_tp: ATR multiplier for take profit
        min_rr_ratio: Minimum risk/reward ratio

    Returns:
        Dictionary with entry, stop_loss, take_profit, risk_per_trade, reward_per_trade
    """
    if entry_price is None or df_features is None:
        return None

    # Get ATR from features
    atr = (
        float(df_features["atr_14"].iloc[-1])
        if "atr_14" in df_features.columns
        else 100.0
    )

    # Calculate stop loss and take profit based on signal type
    if signal_type == "LONG":
        stop_loss = entry_price - (atr * atr_multiplier_sl)
        risk_per_trade = entry_price - stop_loss
        reward_per_trade = risk_per_trade * min_rr_ratio
        take_profit = entry_price + reward_per_trade
    else:  # SHORT
        stop_loss = entry_price + (atr * atr_multiplier_sl)
        risk_per_trade = stop_loss - entry_price
        reward_per_trade = risk_per_trade * min_rr_ratio
        take_profit = entry_price - reward_per_trade

    return {
        "entry": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_per_trade": risk_per_trade,
        "reward_per_trade": reward_per_trade,
        "risk_reward_ratio": min_rr_ratio,
    }
