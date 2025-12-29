# ===============================
# RISK MANAGEMENT
# ===============================


def calc_levels(price: float, atr: float, direction: str) -> tuple:
    """
    Calculate SL & TP based on ATR
    """

    if direction.lower() == "long":
        sl = price - (0.25 * atr)
        tp = price + (0.35 * atr)
    else:
        sl = price + (0.25 * atr)
        tp = price - (0.35 * atr)

    return sl, tp
