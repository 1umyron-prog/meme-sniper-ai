from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class TokenProfile(Base):
    __tablename__ = "token_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    token_address: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    dexscreener_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    website_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    twitter_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    telegram_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    discord_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tiktok_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    instagram_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
