from dataclasses import dataclass


@dataclass
class MomentumAnalysis:
    score: int
    level: str
    signals: list[str]
    warnings: list[str]


def _number(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def analyze_momentum(pair: dict) -> MomentumAnalysis:
    """
    Score short-term market momentum from 0 to 100.

    Higher score = stronger apparent momentum.

    This is not a prediction that price will rise.
    """

    liquidity = _number(
        (pair.get("liquidity") or {}).get("usd")
    )

    volume_24h = _number(
        (pair.get("volume") or {}).get("h24")
    )

    txns = pair.get("txns") or {}
    h24 = txns.get("h24") or {}

    buys = _number(h24.get("buys"))
    sells = _number(h24.get("sells"))

    price_change = pair.get("priceChange") or {}

    change_5m = _number(price_change.get("m5"))
    change_1h = _number(price_change.get("h1"))
    change_24h = _number(price_change.get("h24"))

    score = 0
    signals = []
    warnings = []

    # ----------------------------------------
    # LIQUIDITY
    # ----------------------------------------

    if liquidity >= 100_000:
        score += 20
        signals.append("Strong liquidity")

    elif liquidity >= 50_000:
        score += 16
        signals.append("Good liquidity")

    elif liquidity >= 20_000:
        score += 12
        signals.append("Moderate liquidity")

    elif liquidity >= 10_000:
        score += 7
        signals.append("Developing liquidity")

    elif liquidity > 0:
        score += 2
        warnings.append("Thin liquidity")

    else:
        warnings.append("No reported liquidity")

    # ----------------------------------------
    # VOLUME
    # ----------------------------------------

    if volume_24h >= 1_000_000:
        score += 22
        signals.append("Very strong 24h volume")

    elif volume_24h >= 500_000:
        score += 18
        signals.append("Strong 24h volume")

    elif volume_24h >= 100_000:
        score += 14
        signals.append("Healthy 24h volume")

    elif volume_24h >= 25_000:
        score += 9
        signals.append("Developing 24h volume")

    elif volume_24h >= 5_000:
        score += 4

    else:
        warnings.append("Low 24h volume")

    # ----------------------------------------
    # TRANSACTION ACTIVITY
    # ----------------------------------------

    total_trades = buys + sells

    if total_trades >= 10_000:
        score += 15
        signals.append("Very high transaction activity")

    elif total_trades >= 3_000:
        score += 12
        signals.append("Strong transaction activity")

    elif total_trades >= 1_000:
        score += 9
        signals.append("Healthy transaction activity")

    elif total_trades >= 250:
        score += 5

    elif total_trades > 0:
        score += 2
        warnings.append("Low transaction count")

    else:
        warnings.append("No transaction activity")

    # ----------------------------------------
    # BUY PRESSURE
    # ----------------------------------------

    if total_trades > 0:
        buy_ratio = buys / total_trades

        if 0.55 <= buy_ratio <= 0.70:
            score += 12
            signals.append("Positive buy pressure")

        elif 0.50 <= buy_ratio < 0.55:
            score += 7
            signals.append("Slight buy-side advantage")

        elif 0.45 <= buy_ratio < 0.50:
            score += 3

        elif buy_ratio < 0.40:
            score -= 8
            warnings.append("Strong sell-side pressure")

        elif buy_ratio > 0.80:
            score -= 3
            warnings.append(
                "Extreme buy imbalance may be unstable"
            )

    # ----------------------------------------
    # SHORT-TERM PRICE MOMENTUM
    # ----------------------------------------

    if 5 <= change_5m <= 25:
        score += 12
        signals.append("Positive 5m momentum")

    elif 25 < change_5m <= 60:
        score += 8
        signals.append("Strong 5m price acceleration")

    elif change_5m > 60:
        score += 2
        warnings.append("Extreme 5m price spike")

    elif change_5m <= -20:
        score -= 12
        warnings.append("Sharp 5m decline")

    elif change_5m < -5:
        score -= 5
        warnings.append("Negative 5m momentum")

    # ----------------------------------------
    # 1-HOUR MOMENTUM
    # ----------------------------------------

    if 10 <= change_1h <= 75:
        score += 12
        signals.append("Strong 1h momentum")

    elif 75 < change_1h <= 150:
        score += 7
        signals.append("Very strong 1h momentum")

    elif change_1h > 150:
        score -= 2
        warnings.append("Extreme 1h move may be overheated")

    elif change_1h <= -30:
        score -= 12
        warnings.append("Major 1h decline")

    elif change_1h < -10:
        score -= 6
        warnings.append("Weak 1h trend")

    # ----------------------------------------
    # 24-HOUR MOVE / OVERHEATING
    # ----------------------------------------

    if 20 <= change_24h <= 150:
        score += 7
        signals.append("Positive 24h trend")

    elif 150 < change_24h <= 300:
        score += 3
        warnings.append("Large 24h move")

    elif change_24h > 300:
        score -= 10
        warnings.append("Extremely extended 24h move")

    elif change_24h <= -50:
        score -= 10
        warnings.append("Severe 24h decline")

    # ----------------------------------------
    # VOLUME VS LIQUIDITY
    # ----------------------------------------

    if liquidity > 0 and volume_24h > 0:
        ratio = volume_24h / liquidity

        if 1 <= ratio <= 20:
            score += 8
            signals.append(
                "Strong volume relative to liquidity"
            )

        elif 20 < ratio <= 50:
            score += 3
            warnings.append(
                "Very high turnover relative to liquidity"
            )

        elif ratio > 50:
            score -= 8
            warnings.append(
                "Extreme turnover may indicate unstable trading"
            )

        elif ratio < 0.1:
            score -= 5
            warnings.append(
                "Weak volume relative to liquidity"
            )

    score = max(0, min(100, int(score)))

    if score >= 75:
        level = "VERY_STRONG"

    elif score >= 55:
        level = "STRONG"

    elif score >= 35:
        level = "MODERATE"

    elif score >= 20:
        level = "WEAK"

    else:
        level = "VERY_WEAK"

    return MomentumAnalysis(
        score=score,
        level=level,
        signals=signals,
        warnings=warnings,
    )