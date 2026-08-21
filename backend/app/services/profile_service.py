from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.token_profile import TokenProfile


def save_token_profile(
    db: Session,
    profile_data: dict,
) -> TokenProfile:
    token_address = profile_data.get("token_address")

    if not token_address:
        raise ValueError("Profile is missing token_address")

    links = profile_data.get("links") or []

    website_url = None
    twitter_url = None
    telegram_url = None
    discord_url = None
    tiktok_url = None
    instagram_url = None

    for link in links:
        url = link.get("url")
        link_type = (link.get("type") or "").lower()
        label = (link.get("label") or "").lower()

        if not url:
            continue

        if link_type == "twitter":
            twitter_url = url

        elif link_type == "telegram":
            telegram_url = url

        elif link_type == "discord":
            discord_url = url

        elif link_type == "tiktok":
            tiktok_url = url

        elif link_type == "instagram":
            instagram_url = url

        elif label == "website":
            website_url = url

    existing = db.scalar(
        select(TokenProfile).where(
            TokenProfile.token_address == token_address
        )
    )

    if existing:
        existing.description = (
            profile_data.get("description")
            or existing.description
        )

        existing.dexscreener_url = (
            profile_data.get("url")
            or existing.dexscreener_url
        )

        existing.website_url = (
            website_url
            or existing.website_url
        )

        existing.twitter_url = (
            twitter_url
            or existing.twitter_url
        )

        existing.telegram_url = (
            telegram_url
            or existing.telegram_url
        )

        existing.discord_url = (
            discord_url
            or existing.discord_url
        )

        existing.tiktok_url = (
            tiktok_url
            or existing.tiktok_url
        )

        existing.instagram_url = (
            instagram_url
            or existing.instagram_url
        )

        existing.last_seen_at = datetime.utcnow()

        db.commit()
        db.refresh(existing)

        return existing

    profile = TokenProfile(
        token_address=token_address,
        description=profile_data.get("description"),
        dexscreener_url=profile_data.get("url"),
        website_url=website_url,
        twitter_url=twitter_url,
        telegram_url=telegram_url,
        discord_url=discord_url,
        tiktok_url=tiktok_url,
        instagram_url=instagram_url,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile
    