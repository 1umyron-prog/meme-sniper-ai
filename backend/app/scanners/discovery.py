import httpx


LATEST_PROFILES_URL = (
    "https://api.dexscreener.com/token-profiles/latest/v1"
)

PRIMARY_PAIRS_URL = (
    "https://api.dexscreener.com/token-pairs/v1/"
    "solana/{token_address}"
)

FALLBACK_TOKEN_URL = (
    "https://api.dexscreener.com/tokens/v1/"
    "solana/{token_address}"
)


async def discover_solana_tokens() -> list[dict]:
    """
    Discover recent Solana token profiles from DexScreener.
    """

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:
        response = await client.get(
            LATEST_PROFILES_URL
        )

        response.raise_for_status()

        profiles = response.json()

    if not isinstance(profiles, list):
        return []

    discovered = []
    seen = set()

    for profile in profiles:
        if profile.get("chainId") != "solana":
            continue

        token_address = profile.get(
            "tokenAddress"
        )

        if not token_address:
            continue

        if token_address in seen:
            continue

        seen.add(token_address)

        discovered.append({
            "token_address":
                token_address,

            "description":
                profile.get("description"),

            "url":
                profile.get("url"),

            "links":
                profile.get("links")
                or [],
        })

    return discovered


async def fetch_token_pairs(
    token_address: str,
) -> list[dict]:
    """
    Fetch fresh Solana pairs for a token.

    Strategy:

    1. Try DexScreener's token-pairs endpoint.
    2. Keep only pairs where our candidate is baseToken.
    3. If no valid pair is returned, try the tokens/v1
       lookup endpoint as a fallback.
    4. Never return quote-side pools.

    This is important because our database and analyzers
    treat baseToken as the candidate being analyzed.
    """

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        # ------------------------------------------
        # PRIMARY LOOKUP
        # ------------------------------------------

        primary_url = PRIMARY_PAIRS_URL.format(
            token_address=token_address
        )

        try:
            response = await client.get(
                primary_url
            )

            response.raise_for_status()

            primary_pairs = response.json()

            if not isinstance(
                primary_pairs,
                list,
            ):
                primary_pairs = []

        except Exception:
            primary_pairs = []

        valid_primary = _filter_candidate_pairs(
            primary_pairs,
            token_address,
        )

        if valid_primary:
            return valid_primary

        # ------------------------------------------
        # FALLBACK LOOKUP
        # ------------------------------------------

        fallback_url = FALLBACK_TOKEN_URL.format(
            token_address=token_address
        )

        try:
            response = await client.get(
                fallback_url
            )

            response.raise_for_status()

            fallback_pairs = response.json()

            if not isinstance(
                fallback_pairs,
                list,
            ):
                fallback_pairs = []

        except Exception:
            fallback_pairs = []

        return _filter_candidate_pairs(
            fallback_pairs,
            token_address,
        )


def _filter_candidate_pairs(
    pairs: list[dict],
    token_address: str,
) -> list[dict]:
    """
    Keep only legitimate Solana pools where the token
    being scanned is the base token.

    Also removes duplicate pair addresses.
    """

    valid_pairs = []
    seen_pairs = set()

    for pair in pairs:
        if not isinstance(pair, dict):
            continue

        if pair.get("chainId") != "solana":
            continue

        base_token = (
            pair.get("baseToken")
            or {}
        )

        if (
            base_token.get("address")
            != token_address
        ):
            continue

        pair_address = pair.get(
            "pairAddress"
        )

        if not pair_address:
            continue

        if pair_address in seen_pairs:
            continue

        seen_pairs.add(
            pair_address
        )

        valid_pairs.append(
            pair
        )

    return valid_pairs