from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.analyzers.rug_analyzer import analyze_pair
from backend.app.models.pair import Pair


def score_candidates(
    db: Session,
    limit: int = 50,
) -> list[dict]:

    pairs = db.scalars(
        select(Pair)
        .order_by(Pair.discovered_at.desc())
        .limit(limit)
    ).all()

    results = []

    for pair in pairs:
        pair_data = {
            "liquidity": {
                "usd": pair.liquidity_usd,
            },
            "volume": {
                "h24": pair.volume_24h,
            },
            "txns": {
                "h24": {
                    "buys": pair.buys_24h or 0,
                    "sells": pair.sells_24h or 0,
                }
            },
            "priceChange": {
                "h24": pair.price_change_24h,
            },
        }

        analysis = analyze_pair(pair_data)

        results.append({
            "pair_address": pair.pair_address,
            "token_address": pair.token_address,
            "dex": pair.dex_id,
            "liquidity_usd": pair.liquidity_usd,
            "volume_24h": pair.volume_24h,
            "risk_score": analysis.score,
            "risk_level": analysis.risk_level,
            "flags": analysis.flags,
            "positives": analysis.positives,
        })

    results.sort(
        key=lambda item: item["risk_score"]
    )

    return results
