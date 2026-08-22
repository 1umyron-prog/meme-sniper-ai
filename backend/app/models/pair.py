from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class Pair(Base):
    __tablename__ = "pairs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    pair_address: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
    )

    token_address: Mapped[str] = mapped_column(
        String(128),
        index=True,
    )

    dex_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    quote_symbol: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    price_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    liquidity_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    fdv: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    volume_24h: Mapped[float | None] = mapped_column(
        Float,
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

    pair_created_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    # Last time this specific pair was successfully
    # returned by a live market-data request.
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )