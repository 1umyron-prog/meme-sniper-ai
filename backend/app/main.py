from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.analyzers.candidate_scorer import score_candidates
from backend.app.analyzers.momentum_analyzer import analyze_momentum
from backend.app.analyzers.popularity_analyzer import analyze_popularity
from backend.app.analyzers.rug_analyzer import analyze_pair
from backend.app.db.database import engine, get_db
from backend.app.db.init_db import init_db
from backend.app.models.pair import Pair
from backend.app.models.token import Token
from backend.app.models.token_profile import TokenProfile
from backend.app.scanners.dexscreener import search_tokens
from backend.app.services.token_service import save_pair


app = FastAPI(
    title="MemeSniper AI",
    description=(
        "AI-powered meme coin safety, momentum, "
        "popularity, and opportunity scanner"
    ),
    version="0.4.0",
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {
        "name": "MemeSniper AI",
        "status": "online",
        "version": "0.4.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT 1")
            )

        return {
            "database": "connected",
        }

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
                pair = save_pair(
                    db,
                    pair_data,
                )

                saved.append({
                    "pair_address":
                        pair.pair_address,

                    "token_address":
                        pair.token_address,
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
    min_popularity: int = 0,
    limit: int = 25,
    db: Session = Depends(get_db),
):
    """
    Rank safety-screened tokens using:

    - Safety score
    - Momentum score
    - Popularity / social-presence score
    - Combined opportunity score

    Popularity currently measures social/web presence.

    It does NOT yet measure true organic virality,
    follower growth, mention growth, or engagement growth.

    Higher opportunity scores indicate stronger current
    combined signals. They are not predictions or guarantees.
    """

    tokens = db.scalars(
        select(Token)
        .where(
            Token.rug_score.is_not(None)
        )
        .where(
            Token.rug_score <= max_risk
        )
    ).all()

    results = []

    for token in tokens:
        # ------------------------------------------
        # GET TOKEN PAIRS
        # ------------------------------------------

        pairs = db.scalars(
            select(Pair)
            .where(
                Pair.token_address == token.address
            )
        ).all()

        if not pairs:
            continue

        # Prefer the pool with the highest
        # currently reported liquidity.
        best_pair = max(
            pairs,
            key=lambda pair:
                pair.liquidity_usd or 0,
        )

        liquidity = (
            best_pair.liquidity_usd
            or 0
        )

        if liquidity < min_liquidity:
            continue

        # ------------------------------------------
        # MOMENTUM
        # ------------------------------------------

        buys = (
            best_pair.buys_24h
            or 0
        )

        sells = (
            best_pair.sells_24h
            or 0
        )

        total_trades = (
            buys + sells
        )

        buy_ratio = (
            round(
                (buys / total_trades) * 100,
                2,
            )
            if total_trades > 0
            else None
        )

        pair_data = {
            "liquidity": {
                "usd":
                    best_pair.liquidity_usd,
            },

            "volume": {
                "h24":
                    best_pair.volume_24h,
            },

            "txns": {
                "h24": {
                    "buys": buys,
                    "sells": sells,
                }
            },

            "priceChange": {
                "m5":
                    best_pair.price_change_5m,

                "h1":
                    best_pair.price_change_1h,

                "h24":
                    best_pair.price_change_24h,
            },
        }

        momentum = analyze_momentum(
            pair_data
        )

        if momentum.score < min_momentum:
            continue

        # ------------------------------------------
        # SAFETY
        # ------------------------------------------

        rug_risk_score = float(
            token.rug_score
        )

        safety_score = round(
            100 - rug_risk_score,
            2,
        )

        # ------------------------------------------
        # POPULARITY / SOCIAL PRESENCE
        # ------------------------------------------

        profile = db.scalar(
            select(TokenProfile)
            .where(
                TokenProfile.token_address
                == token.address
            )
        )

        if profile:
            popularity = analyze_popularity(
                profile
            )

            popularity_score = (
                popularity.score
            )

            popularity_level = (
                popularity.level
            )

            popularity_signals = (
                popularity.signals
            )

            popularity_warnings = (
                popularity.warnings
            )

            website_url = (
                profile.website_url
            )

            twitter_url = (
                profile.twitter_url
            )

            telegram_url = (
                profile.telegram_url
            )

            discord_url = (
                profile.discord_url
            )

            tiktok_url = (
                profile.tiktok_url
            )

            instagram_url = (
                profile.instagram_url
            )

        else:
            popularity_score = 0
            popularity_level = "MINIMAL"

            popularity_signals = []

            popularity_warnings = [
                "No token profile data available"
            ]

            website_url = None
            twitter_url = None
            telegram_url = None
            discord_url = None
            tiktok_url = None
            instagram_url = None

        if popularity_score < min_popularity:
            continue

        # ------------------------------------------
        # OPPORTUNITY SCORE
        # ------------------------------------------
        #
        # Popularity is intentionally weighted
        # conservatively at this stage.
        #
        # Current popularity measures presence,
        # not organic virality.
        #
        # SAFETY      = 50%
        # MOMENTUM    = 35%
        # POPULARITY  = 15%
        # ------------------------------------------

        opportunity_score = round(
            (safety_score * 0.50)
            + (momentum.score * 0.35)
            + (popularity_score * 0.15),
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

        # ------------------------------------------
        # RESULT
        # ------------------------------------------

        results.append({
            "symbol":
                token.symbol,

            "name":
                token.name,

            "token_address":
                token.address,

            # SAFETY
            "rug_risk_score":
                rug_risk_score,

            "safety_score":
                safety_score,

            # MOMENTUM
            "momentum_score":
                momentum.score,

            "momentum_level":
                momentum.level,

            # POPULARITY
            "popularity_score":
                popularity_score,

            "popularity_level":
                popularity_level,

            # FINAL RANKING
            "opportunity_score":
                opportunity_score,

            "opportunity_level":
                opportunity_level,

            # MARKET DATA
            "liquidity_usd":
                best_pair.liquidity_usd,

            "volume_24h":
                best_pair.volume_24h,

            "buys_24h":
                best_pair.buys_24h,

            "sells_24h":
                best_pair.sells_24h,

            "buy_ratio_percent":
                buy_ratio,

            "price_change_5m":
                best_pair.price_change_5m,

            "price_change_1h":
                best_pair.price_change_1h,

            "price_change_24h":
                best_pair.price_change_24h,

            # PAIR INFO
            "dex":
                best_pair.dex_id,

            "pair_address":
                best_pair.pair_address,

            "pair_created_at":
                best_pair.pair_created_at,

            "discovered_at":
                best_pair.discovered_at,

            # SOCIAL / WEB
            "website_url":
                website_url,

            "twitter_url":
                twitter_url,

            "telegram_url":
                telegram_url,

            "discord_url":
                discord_url,

            "tiktok_url":
                tiktok_url,

            "instagram_url":
                instagram_url,

            # MOMENTUM EXPLANATION
            "momentum_signals":
                momentum.signals,

            "momentum_warnings":
                momentum.warnings,

            # POPULARITY EXPLANATION
            "popularity_signals":
                popularity_signals,

            "popularity_warnings":
                popularity_warnings,
        })

    # ----------------------------------------------
    # SORT BEST OPPORTUNITIES FIRST
    # ----------------------------------------------

    results.sort(
        key=lambda item:
            item["opportunity_score"],
        reverse=True,
    )

    results = results[:limit]

    return {
        "status": "success",

        "filters": {
            "max_risk":
                max_risk,

            "min_liquidity":
                min_liquidity,

            "min_momentum":
                min_momentum,

            "min_popularity":
                min_popularity,

            "limit":
                limit,
        },

        "count":
            len(results),

        "scoring": {
            "safety_weight":
                0.50,

            "momentum_weight":
                0.35,

            "popularity_weight":
                0.15,

            "popularity_stage":
                "social_web_presence",
        },

        "watchlist":
            results,
    }