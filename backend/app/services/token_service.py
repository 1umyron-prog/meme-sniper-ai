from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.pair import Pair
from backend.app.models.token import Token


def save_pair(
    db: Session,
    pair_data: dict,
) -> Pair:
    pair_address = pair_data.get(
        "pairAddress"
    )

    if not pair_address:
        raise ValueError(
            "Pair is missing pairAddress"
        )

    base_token = (
        pair_data.get("baseToken")
        or {}
    )

    quote_token = (
        pair_data.get("quoteToken")
        or {}
    )

    token_address = base_token.get(
        "address"
    )

    if not token_address:
        raise ValueError(
            "Pair is missing token address"
        )

    now = datetime.utcnow()

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

    h24 = (
        txns.get("h24")
        or {}
    )

    # ==========================================
    # TOKEN
    # ==========================================

    token = db.scalar(
        select(Token)
        .where(
            Token.address
            == token_address
        )
    )

    if not token:
        token = Token(
            address=token_address,
            name=base_token.get("name"),
            symbol=base_token.get("symbol"),
            chain=pair_data.get(
                "chainId",
                "solana",
            ),
            price=_float(
                pair_data.get("priceUsd")
            ),
            market_cap=_float(
                pair_data.get("marketCap")
                or pair_data.get("fdv")
            ),
            liquidity=_float(
                liquidity.get("usd")
            ),
            created_at=now,
            last_scan=now,
        )

        db.add(token)
        db.flush()

    else:
        token.name = (
            base_token.get("name")
            or token.name
        )

        token.symbol = (
            base_token.get("symbol")
            or token.symbol
        )

        token.price = _float(
            pair_data.get("priceUsd")
        )

        token.market_cap = _float(
            pair_data.get("marketCap")
            or pair_data.get("fdv")
        )

        token.liquidity = _float(
            liquidity.get("usd")
        )

        token.last_scan = now

    # ==========================================
    # EXISTING PAIR
    # ==========================================

    existing = db.scalar(
        select(Pair)
        .where(
            Pair.pair_address
            == pair_address
        )
    )

    if existing:
        existing.dex_id = (
            pair_data.get("dexId")
            or existing.dex_id
        )

        existing.quote_symbol = (
            quote_token.get("symbol")
            or existing.quote_symbol
        )

        existing.price_usd = _float(
            pair_data.get("priceUsd")
        )

        existing.liquidity_usd = _float(
            liquidity.get("usd")
        )

        existing.fdv = _float(
            pair_data.get("fdv")
        )

        existing.volume_24h = _float(
            volume.get("h24")
        )

        existing.buys_24h = _int(
            h24.get("buys")
        )

        existing.sells_24h = _int(
            h24.get("sells")
        )

        existing.price_change_5m = _float(
            price_change.get("m5")
        )

        existing.price_change_1h = _float(
            price_change.get("h1")
        )

        existing.price_change_24h = _float(
            price_change.get("h24")
        )

        pair_created_at = (
            _datetime_from_ms(
                pair_data.get(
                    "pairCreatedAt"
                )
            )
        )

        if pair_created_at is not None:
            existing.pair_created_at = (
                pair_created_at
            )

        # Critical:
        # only a successful live response reaches here.
        existing.last_refreshed_at = now

        db.commit()
        db.refresh(existing)

        return existing

    # ==========================================
    # NEW PAIR
    # ==========================================

    pair = Pair(
        pair_address=pair_address,
        token_address=token_address,
        dex_id=pair_data.get("dexId"),
        quote_symbol=quote_token.get(
            "symbol"
        ),
        price_usd=_float(
            pair_data.get("priceUsd")
        ),
        liquidity_usd=_float(
            liquidity.get("usd")
        ),
        fdv=_float(
            pair_data.get("fdv")
        ),
        volume_24h=_float(
            volume.get("h24")
        ),
        buys_24h=_int(
            h24.get("buys")
        ),
        sells_24h=_int(
            h24.get("sells")
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
        pair_created_at=_datetime_from_ms(
            pair_data.get(
                "pairCreatedAt"
            )
        ),
        last_refreshed_at=now,
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


def _int(value):
    if value is None:
        return None

    try:
        return int(value)

    except (TypeError, ValueError):
        return None


def _datetime_from_ms(value):
    if value is None:
        return None

    try:
        return datetime.fromtimestamp(
            float(value) / 1000,
            tz=timezone.utc,
        ).replace(
            tzinfo=None
        )

    except (
        TypeError,
        ValueError,
        OSError,
    ):
        return None