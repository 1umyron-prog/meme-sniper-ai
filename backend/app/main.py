from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.analyzers.candidate_scorer import score_candidates
from backend.app.analyzers.momentum_analyzer import analyze_momentum
from backend.app.analyzers.rug_analyzer import analyze_pair
from backend.app.db.database import engine, get_db
from backend.app.db.init_db import init_db
from backend.app.models.pair import Pair
from backend.app.models.token import Token
from backend.app.scanners.dexscreener import search_tokens
from backend.app.services.token_service import save_pair


app = FastAPI(
    title="MemeSniper AI",
    description="AI-powered meme coin risk and momentum scanner",
    version="0.3.0",
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {
        "name": "MemeSniper AI",
        "status": "online",
        "version": "0.3.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {"database": "connected"}

    except Exception as error:
        return {
            "database": "error",
            "message": str(error),
        }


@app.get("/scanner/search")
async def scanner_search(
    query: str,
    db: Session = Depends(get_db),
):
    try:
        data = await search_tokens(query)

        pairs = data.get("pairs", [])
        saved = []

        for pair_data in pairs:
            try:
                pair = save_pair(db, pair_data)

                saved.append({
                    "pair_address": pair.pair_address,
                    "token_address": pair.token_address,
                })

            except ValueError:
                continue

        return {
            "status": "success",
            "query": query,
            "pairs_found": len(pairs),
            "pairs_saved": len(saved),
            "saved": saved,
        }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }


@app.post("/analyzer/rug")
def rug_analysis(pair: dict):
    analysis = analyze_pair(pair)

    return {
        "risk_score": analysis.score,
        "risk_level": analysis.risk_level,
        "flags": analysis.flags,
        "positives": analysis.positives,
    }


@app.get("/candidates")
def candidates(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return {
        "status": "success",
        "candidates": score_candidates(
            db,
            limit=limit,
        ),
    }


@app.get("/watchlist")
def watchlist(
    max_risk: float = 25,
    min_liquidity: float = 0,
    min_momentum: int = 0,
    limit: int = 25,
    db: Session = Depends(get_db),
):
    """
    Rank automatically safety-screened tokens using:

    - Safety score
    - Momentum score
    - Opportunity score

    Higher opportunity score means stronger current signals.
    It is not a prediction or guarantee of future price gains.
    """

    tokens = db.scalars(
        select(Token)
        .where(Token.rug_score.is_not(None))
        .where(Token.rug_score <= max_risk)
    ).all()

    results = []

    for token in tokens:
        pairs = db.scalars(
            select(Pair)
            .where(Pair.token_address == token.address)
        ).all()

        if not pairs:
            continue

        # Prefer the pool with the highest reported liquidity.
        best_pair = max(
            pairs,
            key=lambda pair: pair.liquidity_usd or 0,
        )

        liquidity = best_pair.liquidity_usd or 0

        if liquidity < min_liquidity:
            continue

        buys = best_pair.buys_24h or 0
        sells = best_pair.sells_24h or 0

        total_trades = buys + sells

        buy_ratio = (
            round((buys / total_trades) * 100, 2)
            if total_trades > 0
            else None
        )

        pair_data = {
            "liquidity": {
                "usd": best_pair.liquidity_usd,
            },
            "volume": {
                "h24": best_pair.volume_24h,
            },
            "txns": {
                "h24": {
                    "buys": buys,
                    "sells": sells,
                }
            },
            "priceChange": {
                "m5": best_pair.price_change_5m,
                "h1": best_pair.price_change_1h,
                "h24": best_pair.price_change_24h,
            },
        }

        momentum = analyze_momentum(pair_data)

        if momentum.score < min_momentum:
            continue

        rug_risk_score = float(token.rug_score)

        # Convert risk into a positive safety score.
        safety_score = round(
            100 - rug_risk_score,
            2,
        )

        # Initial opportunity ranking.
        #
        # Safety matters slightly more than momentum because
        # avoiding obvious high-risk tokens is our first priority.
        opportunity_score = round(
            (safety_score * 0.55)
            + (momentum.score * 0.45),
            2,
        )

        if opportunity_score >= 80:
            opportunity_level = "HIGH"

        elif opportunity_score >= 65:
            opportunity_level = "PROMISING"

        elif opportunity_score >= 50:
            opportunity_level = "WATCH"

        else:
            opportunity_level = "WEAK"

        results.append({
            "symbol": token.symbol,
            "name": token.name,
            "token_address": token.address,

            "rug_risk_score": rug_risk_score,
            "safety_score": safety_score,

            "momentum_score": momentum.score,
            "momentum_level": momentum.level,

            "opportunity_score": opportunity_score,
            "opportunity_level": opportunity_level,

            "liquidity_usd": best_pair.liquidity_usd,
            "volume_24h": best_pair.volume_24h,

            "buys_24h": best_pair.buys_24h,
            "sells_24h": best_pair.sells_24h,
            "buy_ratio_percent": buy_ratio,

            "price_change_5m":
                best_pair.price_change_5m,

            "price_change_1h":
                best_pair.price_change_1h,

            "price_change_24h":
                best_pair.price_change_24h,

            "dex": best_pair.dex_id,
            "pair_address": best_pair.pair_address,

            "pair_created_at":
                best_pair.pair_created_at,

            "discovered_at":
                best_pair.discovered_at,

            "momentum_signals":
                momentum.signals,

            "momentum_warnings":
                momentum.warnings,
        })

    # Highest opportunity score first.
    results.sort(
        key=lambda item: item["opportunity_score"],
        reverse=True,
    )

    results = results[:limit]

    return {
        "status": "success",

        "filters": {
            "max_risk": max_risk,
            "min_liquidity": min_liquidity,
            "min_momentum": min_momentum,
            "limit": limit,
        },

        "count": len(results),

        "scoring": {
            "safety_weight": 0.55,
            "momentum_weight": 0.45,
        },

        "watchlist": results,
    }