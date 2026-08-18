from backend.app.analyzers.owner_classifier import classify_owner
from backend.app.analyzers.solana_safety import (
    get_largest_account_owners,
    helius_rpc,
)


EXCLUDED_PROTOCOL_CLASSES = {
    "liquidity_pool",
    "bonding_curve",
}


async def analyze_adjusted_holder_concentration(
    token_address: str,
) -> dict:
    supply_result = await helius_rpc(
        "getTokenSupply",
        [token_address],
    )

    supply_info = supply_result.get("value") or {}

    total_supply = float(
        supply_info.get("uiAmountString") or 0
    )

    accounts = await get_largest_account_owners(
        token_address
    )

    analyzed = []
    excluded = []
    ordinary = []

    for account in accounts:
        owner = account.get("owner")
        amount = float(account.get("amount") or 0)

        if not owner:
            continue

        percent = (
            (amount / total_supply) * 100
            if total_supply > 0
            else 0
        )

        classification = await classify_owner(owner)

        record = {
            "token_account": account.get("token_account"),
            "owner": owner,
            "amount": amount,
            "percent_of_supply": round(percent, 2),
            "classification": classification["classification"],
            "protocol": classification.get("protocol"),
            "account_program":
                classification.get("account_program"),
        }

        analyzed.append(record)

        if (
            classification["classification"]
            in EXCLUDED_PROTOCOL_CLASSES
        ):
            excluded.append(record)
        else:
            ordinary.append(record)

    ordinary.sort(
        key=lambda item: item["percent_of_supply"],
        reverse=True,
    )

    largest_non_protocol = (
        ordinary[0]["percent_of_supply"]
        if ordinary
        else 0
    )

    top_5_non_protocol = sum(
        item["percent_of_supply"]
        for item in ordinary[:5]
    )

    top_10_non_protocol = sum(
        item["percent_of_supply"]
        for item in ordinary[:10]
    )

    risk_score = 0
    flags = []
    positives = []

    if largest_non_protocol >= 25:
        risk_score += 50
        flags.append(
            "A non-protocol owner controls at least 25% of supply"
        )

    elif largest_non_protocol >= 10:
        risk_score += 30
        flags.append(
            "A non-protocol owner controls at least 10% of supply"
        )

    elif largest_non_protocol >= 5:
        risk_score += 15
        flags.append(
            "Largest non-protocol owner exceeds 5% of supply"
        )

    else:
        positives.append(
            "Largest non-protocol owner is below 5% of supply"
        )

    if top_5_non_protocol >= 50:
        risk_score += 30
        flags.append(
            "Top 5 non-protocol owners control at least 50% of supply"
        )

    elif top_5_non_protocol >= 30:
        risk_score += 20
        flags.append(
            "Top 5 non-protocol owners control at least 30% of supply"
        )

    elif top_5_non_protocol < 20:
        positives.append(
            "Top 5 non-protocol concentration is below 20%"
        )

    if top_10_non_protocol >= 60:
        risk_score += 20
        flags.append(
            "Top 10 non-protocol owners control at least 60% of supply"
        )

    elif top_10_non_protocol < 35:
        positives.append(
            "Top 10 non-protocol concentration is below 35%"
        )

    risk_score = min(risk_score, 100)

    if risk_score <= 20:
        risk_level = "LOW"
    elif risk_score <= 45:
        risk_level = "MODERATE"
    elif risk_score <= 70:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    return {
        "token_address": token_address,
        "total_supply": total_supply,

        "adjusted_metrics": {
            "largest_non_protocol_percent":
                round(largest_non_protocol, 2),
            "top_5_non_protocol_percent":
                round(top_5_non_protocol, 2),
            "top_10_non_protocol_percent":
                round(top_10_non_protocol, 2),
        },

        "holder_risk_score": risk_score,
        "holder_risk_level": risk_level,

        "excluded_protocol_accounts": excluded,
        "non_protocol_accounts": ordinary,

        "flags": flags,
        "positives": positives,
    }