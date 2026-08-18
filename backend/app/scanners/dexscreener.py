import httpx


DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/search"


async def search_tokens(query: str) -> dict:
    """
    Search DexScreener and return Solana pairs only.
    """

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            DEXSCREENER_URL,
            params={"q": query},
        )

        response.raise_for_status()

        data = response.json()

        solana_pairs = [
            pair
            for pair in data.get("pairs", [])
            if pair.get("chainId") == "solana"
        ]

        return {
            "pairs": solana_pairs
        }