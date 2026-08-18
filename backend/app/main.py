from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.analyzers.rug_analyzer import analyze_pair
from backend.app.analyzers.candidate_scorer import score_candidates
from backend.app.db.database import engine, get_db
from backend.app.db.init_db import init_db
from backend.app.models.pair import Pair
from backend.app.models.token import Token
from backend.app.scanners.dexscreener import search_tokens
from backend.app.services.token_service import save_pair


app = FastAPI(
    title="MemeSniper AI",
    description="AI-powered meme coin risk and momentum scanner",
    version="0.2.0",
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {
        "name": "MemeSniper AI",
        "status": "online",
        "version": "0.2.0",
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
    limit: int = 25,
    db: Session = Depends(get_db),
):
    """
    Return automatically analyzed tokens whose stored rug score
    is at or below the requested maximum risk threshold.
    """

    tokens = db.scalars(
        select(Token)
        .where(Token.rug_score.is_not(None))
        .where(Token.rug_score <= max_risk)
        .order_by(Token.rug_score.asc())
        .limit(limit * 3)
    ).all()

    results = []

    for token in tokens:
        pairs = db.scalars(
            select(Pair)
            .where(Pair.token_address == token.address)
        ).all()

        if not pairs:
            continue

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

        results.append({
            "symbol": token.symbol,
            "name": token.name,
            "token_address": token.address,
            "rug_risk_score": token.rug_score,
            "liquidity_usd": best_pair.liquidity_usd,
            "volume_24h": best_pair.volume_24h,
            "buys_24h": best_pair.buys_24h,
            "sells_24h": best_pair.sells_24h,
            "buy_ratio_percent": buy_ratio,
            "price_change_5m": best_pair.price_change_5m,
            "price_change_1h": best_pair.price_change_1h,
            "price_change_24h": best_pair.price_change_24h,
            "dex": best_pair.dex_id,
            "pair_address": best_pair.pair_address,
            "pair_created_at": best_pair.pair_created_at,
            "discovered_at": best_pair.discovered_at,
        })

        if len(results) >= limit:
            break

    return {
        "status": "success",
        "filters": {
            "max_risk": max_risk,
            "min_liquidity": min_liquidity,
            "limit": limit,
        },
        "count": len(results),
        "watchlist": results,
    }