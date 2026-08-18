from backend.app.analyzers.rug_analyzer import analyze_pair
from backend.app.analyzers.solana_safety import (
    analyze_holder_concentration,
    analyze_token_authorities,
)


async def analyze_token_safety(
    token_address: str,
    pair_data: dict,
) -> dict:
    """
    Combine market, holder, and token-authority signals.

    Higher rug_risk_score = higher apparent risk.
    """

    market = analyze_pair(pair_data)

    holders = await analyze_holder_concentration(
        token_address
    )

    authorities = await analyze_token_authorities(
        token_address
    )

    market_score = market.score
    holder_score = holders["holder_risk_score"]
    authority_score = authorities["authority_risk_score"]

    # Weighted risk score.
    # Holder and authority data matter more than market structure.
    combined_score = round(
        (market_score * 0.25)
        + (holder_score * 0.40)
        + (authority_score * 0.35)
    )

    combined_score = max(
        0,
        min(100, combined_score),
    )

    red_flags = []
    green_flags = []

    red_flags.extend(market.flags)
    red_flags.extend(holders["flags"])
    red_flags.extend(authorities["flags"])

    green_flags.extend(market.positives)
    green_flags.extend(holders["positives"])
    green_flags.extend(authorities["positives"])

    if combined_score <= 20:
        risk_level = "LOW"
    elif combined_score <= 45:
        risk_level = "MODERATE"
    elif combined_score <= 70:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    # Until large token accounts are resolved to their owners,
    # holder concentration has uncertainty.
    confidence = "MEDIUM"

    if authority_score > 0:
        confidence = "HIGH"

    return {
        "token_address": token_address,
        "rug_risk_score": combined_score,
        "rug_risk_level": risk_level,
        "confidence": confidence,

        "components": {
            "market_risk": market_score,
            "holder_risk": holder_score,
            "authority_risk": authority_score,
        },

        "holder_metrics": {
            "largest_account_percent":
                holders["largest_account_percent"],
            "top_5_accounts_percent":
                holders["top_5_accounts_percent"],
            "top_10_accounts_percent":
                holders["top_10_accounts_percent"],
        },

        "authority_metrics": {
            "mint_authority":
                authorities["mint_authority"],
            "freeze_authority":
                authorities["freeze_authority"],
        },

        "red_flags": list(dict.fromkeys(red_flags)),
        "green_flags": list(dict.fromkeys(green_flags)),
    }