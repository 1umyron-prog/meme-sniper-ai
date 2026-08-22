from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.attention_snapshot import AttentionSnapshot


@dataclass
class AttentionAnalysis:
    score: int
    organic_score: int
    level: str
    history_status: str
    promotion_level: str
    signals: list[str]
    warnings: list[str]
    metrics: dict


def analyze_attention(
    db: Session,
    token_address: str,
) -> AttentionAnalysis:
    """
    Measure market-attention acceleration using repeated
    snapshots.

    This is NOT social-media virality yet.

    It measures:
    - short-term volume intensity
    - short-term transaction activity
    - buy pressure
    - liquidity
    - changes versus ~5m, ~15m and ~60m ago
    - paid/promoted visibility separately
    """

    snapshots = list(
        db.scalars(
            select(AttentionSnapshot)
            .where(
                AttentionSnapshot.token_address
                == token_address
            )
            .order_by(
                AttentionSnapshot.captured_at.desc()
            )
            .limit(120)
        ).all()
    )

    if not snapshots:
        return AttentionAnalysis(
            score=0,
            organic_score=0,
            level="NO_DATA",
            history_status="NO_DATA",
            promotion_level="UNKNOWN",
            signals=[],
            warnings=[
                "No attention snapshots available"
            ],
            metrics={},
        )

    current = snapshots[0]

    score = 0
    signals = []
    warnings = []

    # --------------------------------------------------
    # CURRENT MARKET ATTENTION
    # --------------------------------------------------

    liquidity = _float(
        current.liquidity_usd
    ) or 0

    volume_5m = _float(
        current.volume_5m
    ) or 0

    buys_5m = _int(
        current.buys_5m
    ) or 0

    sells_5m = _int(
        current.sells_5m
    ) or 0

    trades_5m = (
        buys_5m + sells_5m
    )

    # Liquidity quality
    if liquidity >= 100_000:
        score += 5
        signals.append(
            "Deep current liquidity"
        )

    elif liquidity >= 25_000:
        score += 4
        signals.append(
            "Healthy current liquidity"
        )

    elif liquidity >= 10_000:
        score += 3
        signals.append(
            "Developing current liquidity"
        )

    elif liquidity > 0:
        score += 1
        warnings.append(
            "Thin liquidity"
        )

    # 5-minute volume
    if volume_5m >= 100_000:
        score += 10
        signals.append(
            "Exceptional 5m trading volume"
        )

    elif volume_5m >= 25_000:
        score += 8
        signals.append(
            "Very strong 5m trading volume"
        )

    elif volume_5m >= 5_000:
        score += 6
        signals.append(
            "Strong 5m trading volume"
        )

    elif volume_5m >= 1_000:
        score += 3
        signals.append(
            "Developing 5m trading volume"
        )

    # 5-minute transaction activity
    if trades_5m >= 1000:
        score += 10
        signals.append(
            "Exceptional 5m transaction activity"
        )

    elif trades_5m >= 300:
        score += 8
        signals.append(
            "Very high 5m transaction activity"
        )

    elif trades_5m >= 100:
        score += 6
        signals.append(
            "Strong 5m transaction activity"
        )

    elif trades_5m >= 25:
        score += 3
        signals.append(
            "Developing 5m transaction activity"
        )

    # Buy pressure
    if trades_5m > 0:
        buy_ratio = (
            buys_5m / trades_5m
        )

        if 0.52 <= buy_ratio <= 0.68:
            score += 5
            signals.append(
                "Healthy short-term buy pressure"
            )

        elif 0.68 < buy_ratio <= 0.80:
            score += 3
            signals.append(
                "Strong short-term buy pressure"
            )

        elif buy_ratio > 0.85:
            warnings.append(
                "Extreme short-term buy imbalance"
            )

        elif buy_ratio < 0.40:
            warnings.append(
                "Short-term sell pressure"
            )

    else:
        buy_ratio = None

    # --------------------------------------------------
    # HISTORICAL COMPARISONS
    # --------------------------------------------------

    comparison_windows = {}

    window_definitions = [
        (5, 3),
        (15, 6),
        (60, 20),
    ]

    for minutes, tolerance in window_definitions:
        previous = _find_snapshot_near_age(
            current=current,
            snapshots=snapshots[1:],
            target_minutes=minutes,
            tolerance_minutes=tolerance,
        )

        if previous is None:
            comparison_windows[
                f"{minutes}m"
            ] = None

            continue

        comparison = _compare_snapshots(
            current=current,
            previous=previous,
        )

        comparison_windows[
            f"{minutes}m"
        ] = comparison

        window_score = 0

        volume_growth = comparison[
            "volume_5m_change_percent"
        ]

        trade_growth = comparison[
            "trades_5m_change_percent"
        ]

        liquidity_growth = comparison[
            "liquidity_change_percent"
        ]

        # ------------------------------------------
        # VOLUME ACCELERATION
        # ------------------------------------------

        if volume_growth is not None:
            if volume_growth >= 200:
                window_score += 8
                signals.append(
                    f"Explosive 5m volume growth vs {minutes}m ago"
                )

            elif volume_growth >= 100:
                window_score += 7
                signals.append(
                    f"5m volume doubled vs {minutes}m ago"
                )

            elif volume_growth >= 50:
                window_score += 5
                signals.append(
                    f"Strong volume acceleration vs {minutes}m ago"
                )

            elif volume_growth >= 20:
                window_score += 3
                signals.append(
                    f"Volume increasing vs {minutes}m ago"
                )

            elif volume_growth <= -50:
                window_score -= 4
                warnings.append(
                    f"Volume contracting sharply vs {minutes}m ago"
                )

        # ------------------------------------------
        # TRANSACTION ACCELERATION
        # ------------------------------------------

        if trade_growth is not None:
            if trade_growth >= 150:
                window_score += 7
                signals.append(
                    f"Explosive transaction growth vs {minutes}m ago"
                )

            elif trade_growth >= 75:
                window_score += 6
                signals.append(
                    f"Very strong transaction acceleration vs {minutes}m ago"
                )

            elif trade_growth >= 30:
                window_score += 4
                signals.append(
                    f"Transaction activity rising vs {minutes}m ago"
                )

            elif trade_growth >= 10:
                window_score += 2

            elif trade_growth <= -40:
                window_score -= 4
                warnings.append(
                    f"Transactions contracting vs {minutes}m ago"
                )

        # ------------------------------------------
        # LIQUIDITY GROWTH
        # ------------------------------------------

        if liquidity_growth is not None:
            if liquidity_growth >= 20:
                window_score += 5
                signals.append(
                    f"Strong liquidity growth vs {minutes}m ago"
                )

            elif liquidity_growth >= 10:
                window_score += 4
                signals.append(
                    f"Liquidity expanding vs {minutes}m ago"
                )

            elif liquidity_growth >= 3:
                window_score += 2

            elif liquidity_growth <= -20:
                window_score -= 4
                warnings.append(
                    f"Liquidity falling sharply vs {minutes}m ago"
                )

        # Maximum historical contribution per window.
        window_score = max(
            -10,
            min(20, window_score),
        )

        score += window_score

    # --------------------------------------------------
    # HISTORY QUALITY
    # --------------------------------------------------

    available_windows = sum(
        value is not None
        for value in comparison_windows.values()
    )

    if available_windows == 0:
        history_status = "BUILDING"

        warnings.append(
            "Not enough history for acceleration analysis yet"
        )

    elif available_windows == 1:
        history_status = "EARLY"

    elif available_windows == 2:
        history_status = "PARTIAL"

    else:
        history_status = "FULL"

    # --------------------------------------------------
    # PROMOTION / PAID VISIBILITY
    # --------------------------------------------------

    promotion_penalty = 0

    active_boosts = (
        _int(current.active_boosts)
        or 0
    )

    if current.is_latest_boosted is True:
        promotion_penalty += 8

        warnings.append(
            "Token appears in latest DexScreener boosts"
        )

    if current.is_top_boosted is True:
        promotion_penalty += 10

        warnings.append(
            "Token appears in top DexScreener boosts"
        )

    if active_boosts > 0:
        promotion_penalty += 5

        warnings.append(
            "Active DexScreener boost detected"
        )

    promotion_penalty = min(
        20,
        promotion_penalty,
    )

    if promotion_penalty >= 15:
        promotion_level = "HIGH"

    elif promotion_penalty > 0:
        promotion_level = "PRESENT"

    else:
        if (
            current.is_latest_boosted is None
            and current.is_top_boosted is None
        ):
            promotion_level = "UNKNOWN"

        else:
            promotion_level = "NONE"

    # Raw attention score.
    score = max(
        0,
        min(100, round(score)),
    )

    # Organic-adjusted attention score.
    organic_score = max(
        0,
        score - promotion_penalty,
    )

    # --------------------------------------------------
    # ATTENTION LEVEL
    # --------------------------------------------------

    if organic_score >= 75:
        level = "SURGING"

    elif organic_score >= 55:
        level = "STRONG"

    elif organic_score >= 35:
        level = "BUILDING"

    elif organic_score >= 20:
        level = "EARLY"

    else:
        level = "QUIET"

    metrics = {
        "snapshot_count":
            len(snapshots),

        "latest_snapshot":
            current.captured_at,

        "liquidity_usd":
            liquidity,

        "volume_5m":
            volume_5m,

        "trades_5m":
            trades_5m,

        "buys_5m":
            buys_5m,

        "sells_5m":
            sells_5m,

        "buy_ratio_percent":
            (
                round(
                    buy_ratio * 100,
                    2,
                )
                if buy_ratio is not None
                else None
            ),

        "promotion_penalty":
            promotion_penalty,

        "active_boosts":
            active_boosts,

        "is_latest_boosted":
            current.is_latest_boosted,

        "is_top_boosted":
            current.is_top_boosted,

        "latest_boost_amount":
            current.latest_boost_amount,

        "total_boost_amount":
            current.total_boost_amount,

        "comparison_windows":
            comparison_windows,
    }

    return AttentionAnalysis(
        score=score,
        organic_score=organic_score,
        level=level,
        history_status=history_status,
        promotion_level=promotion_level,
        signals=_dedupe(signals),
        warnings=_dedupe(warnings),
        metrics=metrics,
    )


def _find_snapshot_near_age(
    current,
    snapshots,
    target_minutes,
    tolerance_minutes,
):
    target_time = (
        current.captured_at
        - timedelta(
            minutes=target_minutes
        )
    )

    best = None
    best_difference = None

    for snapshot in snapshots:
        difference = abs(
            (
                snapshot.captured_at
                - target_time
            ).total_seconds()
        )

        if best_difference is None:
            best = snapshot
            best_difference = difference

        elif difference < best_difference:
            best = snapshot
            best_difference = difference

    if best is None:
        return None

    tolerance_seconds = (
        tolerance_minutes * 60
    )

    if best_difference > tolerance_seconds:
        return None

    return best


def _compare_snapshots(
    current,
    previous,
):
    current_trades = (
        (_int(current.buys_5m) or 0)
        + (_int(current.sells_5m) or 0)
    )

    previous_trades = (
        (_int(previous.buys_5m) or 0)
        + (_int(previous.sells_5m) or 0)
    )

    return {
        "previous_snapshot":
            previous.captured_at,

        "volume_5m_change_percent":
            _percent_change(
                current.volume_5m,
                previous.volume_5m,
                minimum_previous=250,
            ),

        "trades_5m_change_percent":
            _percent_change(
                current_trades,
                previous_trades,
                minimum_previous=10,
            ),

        "liquidity_change_percent":
            _percent_change(
                current.liquidity_usd,
                previous.liquidity_usd,
                minimum_previous=1000,
            ),
    }


def _percent_change(
    current,
    previous,
    minimum_previous=0,
):
    current = _float(current)
    previous = _float(previous)

    if current is None or previous is None:
        return None

    if previous <= 0:
        return None

    if previous < minimum_previous:
        return None

    change = (
        (current - previous)
        / previous
        * 100
    )

    # Prevent tiny baselines from producing absurd
    # percentages that dominate the score.
    return round(
        max(-100, min(500, change)),
        2,
    )


def _float(value):
    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _int(value):
    if value is None:
        return None

    try:
        return int(value)

    except (TypeError, ValueError):
        return None


def _dedupe(values):
    return list(
        dict.fromkeys(values)
    )