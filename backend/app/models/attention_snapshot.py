from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class AttentionSnapshot(Base):
    __tablename__ = "attention_snapshots"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    token_address: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )

    # ------------------------------------------
    # SOCIAL / PROFILE PRESENCE
    # ------------------------------------------

    # NULL means we do not have enough profile
    # data to measure social presence.
    #
    # 0 means we measured it and found essentially
    # no useful social presence.
    social_presence_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    profile_known: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    website_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    twitter_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    telegram_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    discord_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    tiktok_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    instagram_present: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    social_channels: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    # ------------------------------------------
    # DEXSCREENER PAID VISIBILITY
    # ------------------------------------------

    active_boosts: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_latest_boosted: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    is_top_boosted: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    latest_boost_amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    total_boost_amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    recent_community_takeover: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    # ------------------------------------------
    # MARKET ATTENTION
    # ------------------------------------------

    liquidity_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    volume_5m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    volume_1h: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    volume_24h: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    buys_5m: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sells_5m: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    buys_1h: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sells_1h: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    buys_24h: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sells_24h: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    price_change_5m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    price_change_1h: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    price_change_24h: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )