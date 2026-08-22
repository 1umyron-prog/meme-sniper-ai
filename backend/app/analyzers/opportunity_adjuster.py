from dataclasses import dataclass


@dataclass
class OpportunityAdjustment:
    penalty: float
    level: str
    warnings: list[str]
    components: dict


def analyze_opportunity_adjustments(
    *,
    promotion_level: str,
    active_boosts: int | None,
    price_change_5m: float | None,
    price_change_1h: float | None,
    price_change_24h: float | None,
    buy_ratio_percent: float | None,
    attention_history: str,
    attention_metrics: dict | None,
) -> OpportunityAdjustment:
    """
    Adjust the base opportunity score for poor entry conditions.

    Penalizes:

    - paid promotion
    - extreme positive price extension
    - sharp downside trends
    - extreme buy/sell imbalance
    - falling liquidity
    - incomplete attention history

    These penalties do not mean a token is necessarily bad.
    They mean the current entry/setup may be unattractive.
    """

    penalty = 0.0
    warnings = []

    components = {
        "promotion": 0.0,
        "price_extension": 0.0,
        "downside_trend": 0.0,
        "buy_imbalance": 0.0,
        "liquidity_deterioration": 0.0,
        "history": 0.0,
    }

    # ==================================================
    # PAID PROMOTION
    # ==================================================

    promotion = (
        promotion_level
        or "UNKNOWN"
    ).upper()

    boosts = (
        active_boosts
        or 0
    )

    promotion_penalty = 0.0

    if promotion == "HIGH":
        promotion_penalty += 8.0

        warnings.append(
            "Heavy paid visibility detected"
        )

    elif promotion == "PRESENT":
        promotion_penalty += 3.0

        warnings.append(
            "Paid visibility detected"
        )

    if boosts >= 500:
        promotion_penalty += 4.0

        warnings.append(
            "Very large active boost campaign"
        )

    elif boosts >= 100:
        promotion_penalty += 2.0

        warnings.append(
            "Large active boost campaign"
        )

    promotion_penalty = min(
        12.0,
        promotion_penalty,
    )

    components["promotion"] = (
        promotion_penalty
    )

    penalty += promotion_penalty

    # ==================================================
    # PRICE DATA
    # ==================================================

    change_5m = _float(
        price_change_5m
    )

    change_1h = _float(
        price_change_1h
    )

    change_24h = _float(
        price_change_24h
    )

    # ==================================================
    # POSITIVE PRICE EXTENSION
    # ==================================================

    extension_penalty = 0.0

    # --------------------------------------------------
    # 5 MINUTES
    # --------------------------------------------------

    if (
        change_5m is not None
        and change_5m >= 150
    ):
        extension_penalty += 12.0

        warnings.append(
            "Extreme 5m vertical price move"
        )

    elif (
        change_5m is not None
        and change_5m >= 100
    ):
        extension_penalty += 9.0

        warnings.append(
            "Extremely extended 5m price move"
        )

    elif (
        change_5m is not None
        and change_5m >= 60
    ):
        extension_penalty += 6.0

        warnings.append(
            "Very large 5m price extension"
        )

    elif (
        change_5m is not None
        and change_5m >= 30
    ):
        extension_penalty += 3.0

        warnings.append(
            "Large 5m price extension"
        )

    # --------------------------------------------------
    # 1 HOUR
    # --------------------------------------------------

    if (
        change_1h is not None
        and change_1h >= 300
    ):
        extension_penalty += 9.0

        warnings.append(
            "Extreme 1h price extension"
        )

    elif (
        change_1h is not None
        and change_1h >= 200
    ):
        extension_penalty += 7.0

        warnings.append(
            "Extremely extended 1h price move"
        )

    elif (
        change_1h is not None
        and change_1h >= 100
    ):
        extension_penalty += 5.0

        warnings.append(
            "Overheated 1h price move"
        )

    # --------------------------------------------------
    # 24 HOURS
    # --------------------------------------------------

    if (
        change_24h is not None
        and change_24h >= 1000
    ):
        extension_penalty += 10.0

        warnings.append(
            "Extreme 24h price extension"
        )

    elif (
        change_24h is not None
        and change_24h >= 500
    ):
        extension_penalty += 6.0

        warnings.append(
            "Very large 24h price extension"
        )

    elif (
        change_24h is not None
        and change_24h >= 300
    ):
        extension_penalty += 4.0

        warnings.append(
            "Large 24h price extension"
        )

    extension_penalty = min(
        20.0,
        extension_penalty,
    )

    components["price_extension"] = (
        extension_penalty
    )

    penalty += extension_penalty

    # ==================================================
    # DOWNSIDE TREND
    # ==================================================

    downside_penalty = 0.0

    # --------------------------------------------------
    # 5 MINUTES
    # --------------------------------------------------

    if (
        change_5m is not None
        and change_5m <= -30
    ):
        downside_penalty += 5.0

        warnings.append(
            "Sharp 5m downside move"
        )

    elif (
        change_5m is not None
        and change_5m <= -15
    ):
        downside_penalty += 3.0

        warnings.append(
            "Weak short-term price action"
        )

    # --------------------------------------------------
    # 1 HOUR
    # --------------------------------------------------

    if (
        change_1h is not None
        and change_1h <= -50
    ):
        downside_penalty += 6.0

        warnings.append(
            "Severe 1h downtrend"
        )

    elif (
        change_1h is not None
        and change_1h <= -25
    ):
        downside_penalty += 4.0

        warnings.append(
            "Strong 1h downtrend"
        )

    elif (
        change_1h is not None
        and change_1h <= -10
    ):
        downside_penalty += 2.0

        warnings.append(
            "Negative 1h trend"
        )

    # --------------------------------------------------
    # 24 HOURS
    # --------------------------------------------------

    if (
        change_24h is not None
        and change_24h <= -70
    ):
        downside_penalty += 8.0

        warnings.append(
            "Severe 24h price collapse"
        )

    elif (
        change_24h is not None
        and change_24h <= -50
    ):
        downside_penalty += 6.0

        warnings.append(
            "Major 24h downtrend"
        )

    elif (
        change_24h is not None
        and change_24h <= -30
    ):
        downside_penalty += 4.0

        warnings.append(
            "Weak 24h trend"
        )

    downside_penalty = min(
        12.0,
        downside_penalty,
    )

    components["downside_trend"] = (
        downside_penalty
    )

    penalty += downside_penalty

    # ==================================================
    # BUY / SELL IMBALANCE
    # ==================================================

    buy_ratio = _float(
        buy_ratio_percent
    )

    imbalance_penalty = 0.0

    if buy_ratio is not None:

        if buy_ratio >= 90:
            imbalance_penalty = 5.0

            warnings.append(
                "Extreme buy-side imbalance"
            )

        elif buy_ratio >= 85:
            imbalance_penalty = 3.0

            warnings.append(
                "Very high buy-side imbalance"
            )

        elif buy_ratio <= 30:
            imbalance_penalty = 4.0

            warnings.append(
                "Strong sell-side imbalance"
            )

        elif buy_ratio <= 40:
            imbalance_penalty = 2.0

            warnings.append(
                "Elevated sell pressure"
            )

    components["buy_imbalance"] = (
        imbalance_penalty
    )

    penalty += imbalance_penalty

    # ==================================================
    # LIQUIDITY DETERIORATION
    # ==================================================

    liquidity_penalty = 0.0

    metrics = (
        attention_metrics
        or {}
    )

    windows = (
        metrics.get(
            "comparison_windows"
        )
        or {}
    )

    five_minute = (
        windows.get("5m")
        or {}
    )

    liquidity_change_5m = _float(
        five_minute.get(
            "liquidity_change_percent"
        )
    )

    if (
        liquidity_change_5m is not None
        and liquidity_change_5m <= -20
    ):
        liquidity_penalty = 6.0

        warnings.append(
            "Liquidity falling rapidly"
        )

    elif (
        liquidity_change_5m is not None
        and liquidity_change_5m <= -10
    ):
        liquidity_penalty = 3.0

        warnings.append(
            "Short-term liquidity deterioration"
        )

    components[
        "liquidity_deterioration"
    ] = liquidity_penalty

    penalty += liquidity_penalty

    # ==================================================
    # ATTENTION HISTORY
    # ==================================================

    history_penalty = 0.0

    history = (
        attention_history
        or "UNKNOWN"
    ).upper()

    if history == "UNKNOWN":
        history_penalty = 5.0

        warnings.append(
            "Attention history unavailable"
        )

    elif history == "BUILDING":
        history_penalty = 3.0

        warnings.append(
            "Attention history still building"
        )

    elif history == "EARLY":
        history_penalty = 2.0

        warnings.append(
            "Attention history is still early"
        )

    components["history"] = (
        history_penalty
    )

    penalty += history_penalty

    # ==================================================
    # FINAL PENALTY
    # ==================================================

    penalty = round(
        min(
            30.0,
            penalty,
        ),
        2,
    )

    if penalty >= 20:
        level = "SEVERE"

    elif penalty >= 12:
        level = "HIGH"

    elif penalty >= 6:
        level = "MODERATE"

    elif penalty > 0:
        level = "LOW"

    else:
        level = "NONE"

    return OpportunityAdjustment(
        penalty=penalty,
        level=level,
        warnings=_dedupe(
            warnings
        ),
        components=components,
    )


def _float(value):
    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _dedupe(values):
    return list(
        dict.fromkeys(values)
    )