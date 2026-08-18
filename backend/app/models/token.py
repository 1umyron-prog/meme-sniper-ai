from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    address: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    symbol: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    chain: Mapped[str] = mapped_column(
        String(30),
        default="solana",
    )

    price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    market_cap: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    liquidity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    holders: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    top_holder_percent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    rug_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    last_scan: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )