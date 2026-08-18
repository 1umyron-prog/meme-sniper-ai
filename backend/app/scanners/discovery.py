import httpx


LATEST_PROFILES_URL = (
    "https://api.dexscreener.com/token-profiles/latest/v1"
)

TOKEN_PAIRS_URL = (
    "https://api.dexscreener.com/token-pairs/v1/solana/{token_address}"
)


async def discover_solana_tokens() -> list[dict]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(LATEST_PROFILES_URL)
        response.raise_for_status()
        profiles = response.json()

    discovered = []
    seen = set()

    for profile in profiles:
        if profile.get("chainId") != "solana":
            continue

        token_address = profile.get("tokenAddress")

        if not token_address or token_address in seen:
            continue

        seen.add(token_address)

        discovered.append(
            {
                "token_address": token_address,
                "description": profile.get("description"),
                "url": profile.get("url"),
                "links": profile.get("links") or [],
            }
        )

    return discovered


async def fetch_token_pairs(token_address: str) -> list[dict]:
    url = TOKEN_PAIRS_URL.format(
        token_address=token_address
    )

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        pairs = response.json()

    return [
        pair
        for pair in pairs
        if pair.get("chainId") == "solana"
    ]
