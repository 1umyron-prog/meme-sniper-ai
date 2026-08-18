import os

import httpx


HELIUS_RPC_URL = "https://mainnet.helius-rpc.com/"


async def helius_rpc(method: str, params: list):
    api_key = os.getenv("HELIUS_API_KEY")

    if not api_key:
        raise RuntimeError("HELIUS_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            HELIUS_RPC_URL,
            params={"api-key": api_key},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            },
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise RuntimeError(str(data["error"]))

        return data["result"]


async def analyze_holder_concentration(
    token_address: str,
) -> dict:
    supply_result = await helius_rpc(
        "getTokenSupply",
        [token_address],
    )

    largest_result = await helius_rpc(
        "getTokenLargestAccounts",
        [token_address],
    )

    supply_value = supply_result.get("value") or {}

    total_supply = float(
        supply_value.get("uiAmountString") or 0
    )

    largest_accounts = largest_result.get("value") or []

    holder_percentages = []

    if total_supply > 0:
        for account in largest_accounts:
            amount = float(
                account.get("uiAmountString") or 0
            )

            percent = (amount / total_supply) * 100

            holder_percentages.append(percent)

    top_holder_percent = (
        holder_percentages[0]
        if holder_percentages
        else 0.0
    )

    top_5_percent = sum(holder_percentages[:5])
    top_10_percent = sum(holder_percentages[:10])

    risk_score = 0
    flags = []
    positives = []

    if top_holder_percent >= 50:
        risk_score += 50
        flags.append(
            "Single token account controls at least 50% of supply"
        )

    elif top_holder_percent >= 25:
        risk_score += 35
        flags.append(
            "Very high single-account concentration"
        )

    elif top_holder_percent >= 10:
        risk_score += 20
        flags.append(
            "High largest-account concentration"
        )

    else:
        positives.append(
            "Largest token account is below 10% of supply"
        )

    if top_5_percent >= 80:
        risk_score += 30
        flags.append(
            "Top 5 token accounts control at least 80% of supply"
        )

    elif top_5_percent >= 50:
        risk_score += 20
        flags.append(
            "Top 5 token accounts control at least half of supply"
        )

    elif top_5_percent < 30:
        positives.append(
            "Top 5 token-account concentration is relatively low"
        )

    if top_10_percent >= 90:
        risk_score += 20
        flags.append(
            "Top 10 token accounts control at least 90% of supply"
        )

    elif top_10_percent < 50:
        positives.append(
            "Top 10 token-account concentration is below 50%"
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
        "largest_account_percent": round(
            top_holder_percent,
            2,
        ),
        "top_5_accounts_percent": round(
            top_5_percent,
            2,
        ),
        "top_10_accounts_percent": round(
            top_10_percent,
            2,
        ),
        "holder_risk_score": risk_score,
        "holder_risk_level": risk_level,
        "flags": flags,
        "positives": positives,
    }
    
    
async def analyze_token_authorities(
    token_address: str,
) -> dict:
    result = await helius_rpc(
        "getAccountInfo",
        [
            token_address,
            {
                "encoding": "jsonParsed",
            },
        ],
    )

    account = result.get("value")

    if not account:
        raise RuntimeError("Mint account was not found")

    data = account.get("data") or {}
    parsed = data.get("parsed") or {}
    info = parsed.get("info") or {}

    mint_authority = info.get("mintAuthority")
    freeze_authority = info.get("freezeAuthority")
    supply = info.get("supply")
    decimals = info.get("decimals")

    risk_score = 0
    flags = []
    positives = []

    if mint_authority:
        risk_score += 45
        flags.append(
            "Mint authority is still active"
        )
    else:
        positives.append(
            "Mint authority is revoked"
        )

    if freeze_authority:
        risk_score += 35
        flags.append(
            "Freeze authority is still active"
        )
    else:
        positives.append(
            "Freeze authority is disabled"
        )

    risk_score = min(risk_score, 100)

    if risk_score == 0:
        risk_level = "LOW"
    elif risk_score <= 35:
        risk_level = "MODERATE"
    elif risk_score <= 70:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    return {
        "token_address": token_address,
        "mint_authority": mint_authority,
        "freeze_authority": freeze_authority,
        "raw_supply": supply,
        "decimals": decimals,
        "authority_risk_score": risk_score,
        "authority_risk_level": risk_level,
        "flags": flags,
        "positives": positives,
    }