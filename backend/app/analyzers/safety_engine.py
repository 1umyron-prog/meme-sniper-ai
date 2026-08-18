from backend.app.analyzers.rug_analyzer import analyze_pair

from backend.app.analyzers.adjusted_holder_analyzer import (
    analyze_adjusted_holder_concentration,
)

from backend.app.analyzers.solana_safety import (
    analyze_token_authorities,
)


async def analyze_token_safety(
    token_address: str,
    pair_data: dict,
) -> dict:

    # 1. Analyze market behavior
    market = analyze_pair(pair_data)

    # 2. Analyze holders, excluding known protocol accounts
    holders = await analyze_adjusted_holder_concentration(
        token_address
    )

    # 3. Analyze mint/freeze authorities
    authorities = await analyze_token_authorities(
        token_address
    )

    market_score = market.score
    holder_score = holders["holder_risk_score"]
    authority_score = authorities["authority_risk_score"]

    # Combined risk score
    combined_score = round(
        (market_score * 0.25)
        + (holder_score * 0.40)
        + (authority_score * 0.35)
    )

    combined_score = max(
        0,
        min(100, combined_score),
    )

    # Combine flags
    red_flags = []
    green_flags = []

    red_flags.extend(market.flags)
    red_flags.extend(holders["flags"])
    red_flags.extend(authorities["flags"])

    green_flags.extend(market.positives)
    green_flags.extend(holders["positives"])
    green_flags.extend(authorities["positives"])

    # Risk level
    if combined_score <= 20:
        risk_level = "LOW"

    elif combined_score <= 45:
        risk_level = "MODERATE"

    elif combined_score <= 70:
        risk_level = "HIGH"

    else:
        risk_level = "CRITICAL"

    # Confidence level
    confidence = "MEDIUM"

    # Return final safety report
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
            "largest_non_protocol_percent":
                holders["adjusted_metrics"][
                    "largest_non_protocol_percent"
                ],

            "top_5_non_protocol_percent":
                holders["adjusted_metrics"][
                    "top_5_non_protocol_percent"
                ],

            "top_10_non_protocol_percent":
                holders["adjusted_metrics"][
                    "top_10_non_protocol_percent"
                ],
        },

        "excluded_protocol_accounts":
            holders["excluded_protocol_accounts"],

        "authority_metrics": {
            "mint_authority":
                authorities["mint_authority"],

            "freeze_authority":
                authorities["freeze_authority"],
        },

        "red_flags":
            list(dict.fromkeys(red_flags)),

        "green_flags":
            list(dict.fromkeys(green_flags)),
    }