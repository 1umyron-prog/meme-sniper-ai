from dataclasses import dataclass


@dataclass
class RugAnalysis:
    score: int
    risk_level: str
    flags: list[str]
    positives: list[str]


def _number(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def analyze_pair(pair: dict) -> RugAnalysis:
    """
    Analyze market-structure signals for a token pair.

    Score:
        0   = lowest apparent risk
        100 = highest apparent risk

    This is NOT a guarantee that a token is safe.
    It is an initial screening layer.
    """

    liquidity = _number(
        pair.get("liquidity", {}).get("usd")
    )

    volume = _number(
        pair.get("volume", {}).get("h24")
    )

    txns = pair.get("txns", {}).get("h24", {})

    buys = _number(txns.get("buys"))
    sells = _number(txns.get("sells"))

    price_change = _number(
        pair.get("priceChange", {}).get("h24")
    )

    score = 20

    flags = []
    positives = []

    # --------------------------------------------------
    # LIQUIDITY
    # --------------------------------------------------

    if liquidity <= 0:
        score += 35
        flags.append("No reported liquidity")

    elif liquidity < 5_000:
        score += 30
        flags.append("Extremely low liquidity")

    elif liquidity < 20_000:
        score += 20
        flags.append("Low liquidity")

    elif liquidity < 50_000:
        score += 10
        flags.append("Limited liquidity")

    elif liquidity >= 100_000:
        positives.append("Strong reported liquidity")

    elif liquidity >= 50_000:
        positives.append("Reasonable reported liquidity")

    # --------------------------------------------------
    # VOLUME
    # --------------------------------------------------

    if volume <= 0:
        score += 25
        flags.append("No reported 24h volume")

    elif volume < 1_000:
        score += 20
        flags.append("Very low trading activity")

    elif volume < 5_000:
        score += 10
        flags.append("Low trading activity")

    elif volume >= 100_000:
        positives.append("Strong trading activity")

    elif volume >= 10_000:
        positives.append("Healthy trading activity")

    # --------------------------------------------------
    # LIQUIDITY / VOLUME SANITY CHECK
    # --------------------------------------------------

    if liquidity > 0 and volume > 0:

        volume_to_liquidity = volume / liquidity

        if liquidity >= 1_000_000 and volume < 10_000:
            score += 25
            flags.append(
                "Extreme liquidity-to-volume anomaly"
            )

        elif volume_to_liquidity < 0.001:
            score += 20
            flags.append(
                "Extremely low volume relative to liquidity"
            )

        elif volume_to_liquidity < 0.01:
            score += 10
            flags.append(
                "Low volume relative to liquidity"
            )

        elif 0.05 <= volume_to_liquidity <= 20:
            positives.append(
                "Volume appears reasonably supported by liquidity"
            )

    # --------------------------------------------------
    # BUY / SELL BALANCE
    # --------------------------------------------------

    total_transactions = buys + sells

    if total_transactions == 0:

        score += 15
        flags.append("No transaction activity reported")

    else:

        buy_ratio = buys / total_transactions

        if buy_ratio > 0.90:
            score += 15
            flags.append(
                "Extreme buy-side imbalance"
            )

        elif buy_ratio < 0.10:
            score += 15
            flags.append(
                "Extreme sell-side imbalance"
            )

        elif 0.30 <= buy_ratio <= 0.70:
            positives.append(
                "Relatively balanced trading"
            )

    # --------------------------------------------------
    # PRICE MOVEMENT
    # --------------------------------------------------

    if price_change >= 500:
        score += 20
        flags.append(
            "Extreme 24h price increase"
        )

    elif price_change >= 200:
        score += 10
        flags.append(
            "Very large 24h price increase"
        )

    elif price_change <= -70:
        score += 20
        flags.append(
            "Severe 24h price decline"
        )

    # --------------------------------------------------
    # SANITY CHECK
    # --------------------------------------------------

    score = max(0, min(100, int(score)))

    if score <= 25:
        risk_level = "LOW"

    elif score <= 50:
        risk_level = "MODERATE"

    elif score <= 75:
        risk_level = "HIGH"

    else:
        risk_level = "CRITICAL"

    return RugAnalysis(
        score=score,
        risk_level=risk_level,
        flags=flags,
        positives=positives,
    )