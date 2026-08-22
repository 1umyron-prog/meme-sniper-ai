import asyncio

import httpx
from sqlalchemy.orm import Session

from backend.app.analyzers.popularity_analyzer import (
    analyze_popularity,
)
from backend.app.models.attention_snapshot import (
    AttentionSnapshot,
)


DEXSCREENER_BASE = "https://api.dexscreener.com"

LATEST_BOOSTS_URL = (
    f"{DEXSCREENER_BASE}/token-boosts/latest/v1"
)

TOP_BOOSTS_URL = (
    f"{DEXSCREENER_BASE}/token-boosts/top/v1"
)

COMMUNITY_TAKEOVERS_URL = (
    f"{DEXSCREENER_BASE}/community-takeovers/latest/v1"
)


async def fetch_promotion_context() -> dict:
    """
    Fetch global DexScreener visibility/promotion feeds once.

    The scanner will eventually call this once per cycle,
    instead of making these requests separately for every
    token.
    """

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        results = await asyncio.gather(
            _fetch_list(
                client,
                LATEST_BOOSTS_URL,
            ),
            _fetch_list(
                client,
                TOP_BOOSTS_URL,
            ),
            _fetch_list(
                client,
                COMMUNITY_TAKEOVERS_URL,
            ),
        )

    (
        latest_result,
        top_result,
        takeover_result,
    ) = results

    latest_items = latest_result["items"]
    top_items = top_result["items"]
    takeover_items = takeover_result["items"]

    latest_boosts = {}

    for item in latest_items:
        if item.get("chainId") != "solana":
            continue

        token_address = item.get(
            "tokenAddress"
        )

        if not token_address:
            continue

        current = latest_boosts.get(
            token_address
        )

        amount = _float(
            item.get("amount")
        ) or 0

        total_amount = _float(
            item.get("totalAmount")
        ) or 0

        if current is None:
            latest_boosts[token_address] = {
                "amount": amount,
                "total_amount": total_amount,
            }

        else:
            # A token can occur more than once in
            # the latest boost feed.
            current["amount"] += amount

            current["total_amount"] = max(
                current["total_amount"],
                total_amount,
            )

    top_boosted = set()

    for item in top_items:
        if item.get("chainId") != "solana":
            continue

        token_address = item.get(
            "tokenAddress"
        )

        if token_address:
            top_boosted.add(
                token_address
            )

    community_takeovers = set()

    for item in takeover_items:
        if item.get("chainId") != "solana":
            continue

        token_address = item.get(
            "tokenAddress"
        )

        if token_address:
            community_takeovers.add(
                token_address
            )

    return {
        "latest_boosts":
            latest_boosts,

        "top_boosted":
            top_boosted,

        "community_takeovers":
            community_takeovers,

        # These flags allow us to distinguish:
        #
        # False = checked and not found
        # None  = source request failed
        "latest_boosts_available":
            latest_result["available"],

        "top_boosts_available":
            top_result["available"],

        "community_takeovers_available":
            takeover_result["available"],

        "errors": [
            error
            for error in [
                latest_result["error"],
                top_result["error"],
                takeover_result["error"],
            ]
            if error
        ],
    }


def save_attention_snapshot(
    db: Session,
    token_address: str,
    pair_data: dict,
    profile,
    promotion_context: dict,
) -> AttentionSnapshot:
    """
    Store one raw attention snapshot.

    We intentionally store the underlying signals instead
    of only storing a final score. That allows the future
    attention analyzer to compare snapshots over time.
    """

    liquidity = (
        pair_data.get("liquidity")
        or {}
    )

    volume = (
        pair_data.get("volume")
        or {}
    )

    txns = (
        pair_data.get("txns")
        or {}
    )

    price_change = (
        pair_data.get("priceChange")
        or {}
    )

    boosts = (
        pair_data.get("boosts")
        or {}
    )

    txns_5m = (
        txns.get("m5")
        or {}
    )

    txns_1h = (
        txns.get("h1")
        or {}
    )

    txns_24h = (
        txns.get("h24")
        or {}
    )

    # ------------------------------------------
    # PROFILE / SOCIAL PRESENCE
    # ------------------------------------------

    if profile is not None:
        popularity = analyze_popularity(
            profile
        )

        social_presence_score = (
            popularity.score
        )

        profile_known = True

        website_present = bool(
            profile.website_url
        )

        twitter_present = bool(
            profile.twitter_url
        )

        telegram_present = bool(
            profile.telegram_url
        )

        discord_present = bool(
            profile.discord_url
        )

        tiktok_present = bool(
            profile.tiktok_url
        )

        instagram_present = bool(
            profile.instagram_url
        )

        social_channels = sum([
            twitter_present,
            telegram_present,
            discord_present,
            tiktok_present,
            instagram_present,
        ])

    else:
        # IMPORTANT:
        #
        # Unknown is NULL, not zero.
        social_presence_score = None
        profile_known = False

        website_present = False
        twitter_present = False
        telegram_present = False
        discord_present = False
        tiktok_present = False
        instagram_present = False
        social_channels = 0

    # ------------------------------------------
    # BOOST INFORMATION
    # ------------------------------------------

    latest_boosts = (
        promotion_context.get(
            "latest_boosts"
        )
        or {}
    )

    boost_info = latest_boosts.get(
        token_address
    )

    latest_available = (
        promotion_context.get(
            "latest_boosts_available",
            False,
        )
    )

    top_available = (
        promotion_context.get(
            "top_boosts_available",
            False,
        )
    )

    takeover_available = (
        promotion_context.get(
            "community_takeovers_available",
            False,
        )
    )

    if latest_available:
        is_latest_boosted = (
            token_address
            in latest_boosts
        )
    else:
        is_latest_boosted = None

    if top_available:
        is_top_boosted = (
            token_address
            in promotion_context.get(
                "top_boosted",
                set(),
            )
        )
    else:
        is_top_boosted = None

    if takeover_available:
        recent_community_takeover = (
            token_address
            in promotion_context.get(
                "community_takeovers",
                set(),
            )
        )
    else:
        recent_community_takeover = None

    if boost_info:
        latest_boost_amount = (
            boost_info.get("amount")
        )

        total_boost_amount = (
            boost_info.get("total_amount")
        )

    else:
        latest_boost_amount = 0 if latest_available else None
        total_boost_amount = 0 if latest_available else None

    # ------------------------------------------
    # CREATE SNAPSHOT
    # ------------------------------------------

    snapshot = AttentionSnapshot(
        token_address=token_address,

        social_presence_score=
            social_presence_score,

        profile_known=
            profile_known,

        website_present=
            website_present,

        twitter_present=
            twitter_present,

        telegram_present=
            telegram_present,

        discord_present=
            discord_present,

        tiktok_present=
            tiktok_present,

        instagram_present=
            instagram_present,

        social_channels=
            social_channels,

        active_boosts=_int(
            boosts.get("active")
        ),

        is_latest_boosted=
            is_latest_boosted,

        is_top_boosted=
            is_top_boosted,

        latest_boost_amount=
            latest_boost_amount,

        total_boost_amount=
            total_boost_amount,

        recent_community_takeover=
            recent_community_takeover,

        liquidity_usd=_float(
            liquidity.get("usd")
        ),

        volume_5m=_float(
            volume.get("m5")
        ),

        volume_1h=_float(
            volume.get("h1")
        ),

        volume_24h=_float(
            volume.get("h24")
        ),

        buys_5m=_int(
            txns_5m.get("buys")
        ),

        sells_5m=_int(
            txns_5m.get("sells")
        ),

        buys_1h=_int(
            txns_1h.get("buys")
        ),

        sells_1h=_int(
            txns_1h.get("sells")
        ),

        buys_24h=_int(
            txns_24h.get("buys")
        ),

        sells_24h=_int(
            txns_24h.get("sells")
        ),

        price_change_5m=_float(
            price_change.get("m5")
        ),

        price_change_1h=_float(
            price_change.get("h1")
        ),

        price_change_24h=_float(
            price_change.get("h24")
        ),
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return snapshot


async def _fetch_list(
    client: httpx.AsyncClient,
    url: str,
) -> dict:
    try:
        response = await client.get(url)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            data = []

        return {
            "items": data,
            "available": True,
            "error": None,
        }

    except Exception as error:
        return {
            "items": [],
            "available": False,
            "error": f"{url}: {error}",
        }


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