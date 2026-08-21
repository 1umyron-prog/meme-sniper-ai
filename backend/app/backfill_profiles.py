import asyncio

import httpx
from sqlalchemy import select

from backend.app.db.database import SessionLocal
from backend.app.models.token import Token
from backend.app.models.token_profile import TokenProfile
from backend.app.services.profile_service import save_token_profile


DEXSCREENER_TOKENS_URL = (
    "https://api.dexscreener.com/tokens/v1/solana/{addresses}"
)

BATCH_SIZE = 30


def chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def liquidity_value(pair: dict) -> float:
    liquidity = pair.get("liquidity") or {}

    try:
        return float(liquidity.get("usd") or 0)
    except (TypeError, ValueError):
        return 0.0


def build_social_url(platform, handle):
    if not platform or not handle:
        return None

    platform = str(platform).lower().strip()
    handle = str(handle).strip().lstrip("@")

    if not handle:
        return None

    if platform in {"twitter", "x"}:
        return f"https://x.com/{handle}"

    if platform == "telegram":
        return f"https://t.me/{handle}"

    if platform == "instagram":
        return f"https://www.instagram.com/{handle}"

    if platform == "tiktok":
        return f"https://www.tiktok.com/@{handle}"

    return None


def extract_profile(
    token_address: str,
    pairs: list[dict],
) -> dict:
    """
    Convert DexScreener pair info into the same profile
    structure used by our existing profile service.
    """

    matching_pairs = []

    for pair in pairs:
        base_token = pair.get("baseToken") or {}

        if base_token.get("address") == token_address:
            matching_pairs.append(pair)

    matching_pairs.sort(
        key=liquidity_value,
        reverse=True,
    )

    links = []
    seen_urls = set()

    dexscreener_url = None

    for pair in matching_pairs:
        if not dexscreener_url:
            dexscreener_url = pair.get("url")

        info = pair.get("info") or {}

        # ------------------------------------------
        # WEBSITES
        # ------------------------------------------

        websites = info.get("websites") or []

        for website in websites:
            url = website.get("url")

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            links.append({
                "type": "website",
                "label": "website",
                "url": url,
            })

        # ------------------------------------------
        # SOCIALS
        # ------------------------------------------

        socials = info.get("socials") or []

        for social in socials:
            social_type = (
                social.get("type")
                or social.get("platform")
                or ""
            )

            social_type = (
                str(social_type)
                .lower()
                .strip()
            )

            if social_type == "x":
                social_type = "twitter"

            url = social.get("url")

            if not url:
                url = build_social_url(
                    social_type,
                    social.get("handle"),
                )

            if not url or url in seen_urls:
                continue

            seen_urls.add(url)

            links.append({
                "type": social_type,
                "label": social_type,
                "url": url,
            })

    return {
        "token_address": token_address,
        "description": None,
        "url": dexscreener_url,
        "links": links,
    }


async def main():
    db = SessionLocal()

    try:
        # Only backfill tokens that don't already have
        # a TokenProfile record.
        addresses = db.scalars(
            select(Token.address)
            .outerjoin(
                TokenProfile,
                TokenProfile.token_address
                == Token.address,
            )
            .where(
                TokenProfile.id.is_(None)
            )
        ).all()

        addresses = list(addresses)

        print(
            f"Tokens needing profile backfill: {len(addresses)}",
            flush=True,
        )

        if not addresses:
            print(
                "Nothing to backfill.",
                flush=True,
            )
            return

        checked = 0
        profiles_saved = 0
        profiles_with_socials = 0
        no_pairs = 0
        errors = 0

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:

            for batch in chunks(
                addresses,
                BATCH_SIZE,
            ):
                joined_addresses = ",".join(batch)

                url = DEXSCREENER_TOKENS_URL.format(
                    addresses=joined_addresses
                )

                try:
                    response = await client.get(url)
                    response.raise_for_status()

                    data = response.json()

                    if not isinstance(data, list):
                        data = []

                except Exception as error:
                    errors += len(batch)

                    print(
                        f"Batch error: {error}",
                        flush=True,
                    )

                    continue

                # Map returned pairs by candidate base token.
                pairs_by_token = {}

                for pair in data:
                    base_token = (
                        pair.get("baseToken")
                        or {}
                    )

                    address = base_token.get(
                        "address"
                    )

                    if not address:
                        continue

                    pairs_by_token.setdefault(
                        address,
                        [],
                    ).append(pair)

                for token_address in batch:
                    checked += 1

                    token_pairs = pairs_by_token.get(
                        token_address,
                        [],
                    )

                    if not token_pairs:
                        no_pairs += 1
                        continue

                    try:
                        profile_data = extract_profile(
                            token_address,
                            token_pairs,
                        )

                        save_token_profile(
                            db,
                            profile_data,
                        )

                        profiles_saved += 1

                        if profile_data["links"]:
                            profiles_with_socials += 1

                        print(
                            (
                                f"PROFILE: {token_address}"
                                f" | links="
                                f"{len(profile_data['links'])}"
                            ),
                            flush=True,
                        )

                    except Exception as error:
                        db.rollback()
                        errors += 1

                        print(
                            (
                                f"Profile error "
                                f"{token_address}: {error}"
                            ),
                            flush=True,
                        )

                # Gentle pacing.
                await asyncio.sleep(0.25)

        print()
        print(
            (
                "BACKFILL COMPLETE | "
                f"checked={checked} | "
                f"profiles_saved={profiles_saved} | "
                f"with_socials={profiles_with_socials} | "
                f"no_pairs={no_pairs} | "
                f"errors={errors}"
            ),
            flush=True,
        )

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())