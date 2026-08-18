from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.pair import Pair
from backend.app.models.token import Token


def save_pair(db: Session, pair_data: dict) -> Pair:
    pair_address = pair_data.get("pairAddress")

    if not pair_address:
        raise ValueError("Pair is missing pairAddress")

    existing = db.scalar(
        select(Pair).where(
            Pair.pair_address == pair_address
        )
    )

    if existing:
        return existing

    base_token = pair_data.get("baseToken") or {}
    quote_token = pair_data.get("quoteToken") or {}

    token_address = base_token.get("address")

    if not token_address:
        raise ValueError("Pair is missing token address")

    token = db.scalar(
        select(Token).where(
            Token.address == token_address
        )
    )

    if not token:
        token = Token(
            address=token_address,
            name=base_token.get("name"),
            symbol=base_token.get("symbol"),
            chain=pair_data.get("chainId", "solana"),
            created_at=datetime.utcnow(),
            last_scan=datetime.utcnow(),
        )

        db.add(token)
        db.flush()

    liquidity = pair_data.get("liquidity") or {}
    volume = pair_data.get("volume") or {}
    txns = pair_data.get("txns") or {}
    price_change = pair_data.get("priceChange") or {}

    h24 = txns.get("h24") or {}

    pair = Pair(
        pair_address=pair_address,
        token_address=token_address,
        dex_id=pair_data.get("dexId"),
        quote_symbol=quote_token.get("symbol"),
        price_usd=_float(pair_data.get("priceUsd")),
        liquidity_usd=_float(liquidity.get("usd")),
        fdv=_float(pair_data.get("fdv")),
        volume_24h=_float(volume.get("h24")),
        buys_24h=h24.get("buys"),
        sells_24h=h24.get("sells"),
        price_change_5m=_float(price_change.get("m5")),
        price_change_1h=_float(price_change.get("h1")),
        price_change_24h=_float(price_change.get("h24")),
    )

    db.add(pair)
    db.commit()
    db.refresh(pair)

    return pair


def _float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None