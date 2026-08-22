from datetime import datetime, timedelta

from fastapi import Depends, FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.analyzers.attention_analyzer import analyze_attention
from backend.app.analyzers.candidate_scorer import score_candidates
from backend.app.analyzers.momentum_analyzer import analyze_momentum
from backend.app.analyzers.opportunity_adjuster import (
    analyze_opportunity_adjustments,
)
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
        "social presence, attention acceleration, "
        "market freshness, entry quality, "
        "and opportunity scanner"
    ),
    version="0.7.1",
)


# ==========================================================
# STARTUP
# ==========================================================


@app.on_event("startup")
def startup():
    init_db()


# ==========================================================
# BASIC API
# ==========================================================


@app.get("/")
def root():
    return {
        "name": "MemeSniper AI",
        "status": "online",
        "version": "0.7.1",
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


# ==========================================================
# MANUAL TOKEN SEARCH
# ==========================================================


@app.get("/scanner/search")
async def scanner_search(
    query: str,
    db: Session = Depends(get_db),
):
    try:
        data = await search_tokens(
            query
        )

        pairs = data.get(
            "pairs",
            [],
        )

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


# ==========================================================
# MANUAL RUG ANALYZER
# ==========================================================


@app.post("/analyzer/rug")
def rug_analysis(
    pair: dict,
):
    analysis = analyze_pair(
        pair
    )

    return {
        "risk_score":
            analysis.score,

        "risk_level":
            analysis.risk_level,

        "flags":
            analysis.flags,

        "positives":
            analysis.positives,
    }


# ==========================================================
# LEGACY CANDIDATE VIEW
# ==========================================================


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


# ==========================================================
# FULL WATCHLIST
# ==========================================================


@app.get("/watchlist")
def watchlist(
    max_risk: float = 25,
    min_liquidity: float = 0,
    min_momentum: int = 0,
    min_popularity: int = 0,
    min_attention: int = 0,
    min_opportunity: float = 0,
    max_data_age_minutes: int = 5,
    include_stale: bool = False,
    limit: int = 25,
    db: Session = Depends(get_db),
):
    """
    Full MemeSniper opportunity ranking.

    Core opportunity score:
    - Safety
    - Momentum
    - Organic attention
    - Social/web presence

    Entry-quality adjustments:
    - Paid promotion
    - Price extension
    - Buy/sell imbalance
    - Liquidity deterioration
    - Attention-history quality

    Stale market data is excluded by default.

    Scores are screening signals.
    They are not predictions or guarantees.
    """

    # ======================================================
    # FRESHNESS SETTINGS
    # ======================================================

    effective_max_age = max(
        1,
        max_data_age_minutes,
    )

    now = datetime.utcnow()

    freshness_cutoff = (
        now
        - timedelta(
            minutes=effective_max_age
        )
    )

    # ======================================================
    # SAFETY-SCREENED TOKENS
    # ======================================================

    tokens = db.scalars(
        select(Token)
        .where(
            Token.rug_score.is_not(None)
        )
        .where(
            Token.rug_score
            <= max_risk
        )
    ).all()

    results = []

    stale_tokens_skipped = 0

    # ======================================================
    # PROCESS TOKENS
    # ======================================================

    for token in tokens:

        # --------------------------------------------------
        # PAIRS
        # --------------------------------------------------

        pairs = db.scalars(
            select(Pair)
            .where(
                Pair.token_address
                == token.address
            )
        ).all()

        if not pairs:
            continue

        # --------------------------------------------------
        # LIVE PAIR FILTER
        # --------------------------------------------------

        live_pairs = [
            pair
            for pair in pairs
            if (
                pair.last_refreshed_at
                is not None
                and
                pair.last_refreshed_at
                >= freshness_cutoff
            )
        ]

        if (
            not live_pairs
            and not include_stale
        ):
            stale_tokens_skipped += 1
            continue

        if live_pairs:
            candidate_pairs = live_pairs

        else:
            # Used only when include_stale=true.
            candidate_pairs = pairs

        # --------------------------------------------------
        # BEST ELIGIBLE PAIR
        # --------------------------------------------------

        best_pair = max(
            candidate_pairs,
            key=lambda pair:
                pair.liquidity_usd
                or 0,
        )

        # --------------------------------------------------
        # MARKET DATA FRESHNESS STATUS
        # --------------------------------------------------

        if (
            best_pair.last_refreshed_at
            is None
        ):
            market_data_status = (
                "UNAVAILABLE"
            )

            market_data_age_minutes = (
                None
            )

        else:
            age_seconds = (
                now
                - best_pair.last_refreshed_at
            ).total_seconds()

            market_data_age_minutes = round(
                max(
                    0,
                    age_seconds / 60,
                ),
                2,
            )

            if (
                best_pair.last_refreshed_at
                >= freshness_cutoff
            ):
                market_data_status = (
                    "LIVE"
                )

            else:
                market_data_status = (
                    "STALE"
                )

        # --------------------------------------------------
        # LIQUIDITY FILTER
        # --------------------------------------------------

        liquidity = (
            best_pair.liquidity_usd
            or 0
        )

        if (
            liquidity
            < min_liquidity
        ):
            continue

        # ==================================================
        # MOMENTUM
        # ==================================================

        buys = (
            best_pair.buys_24h
            or 0
        )

        sells = (
            best_pair.sells_24h
            or 0
        )

        total_trades = (
            buys
            + sells
        )

        buy_ratio = (
            round(
                (
                    buys
                    / total_trades
                )
                * 100,
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
                    "buys":
                        buys,

                    "sells":
                        sells,
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

        if (
            momentum.score
            < min_momentum
        ):
            continue

        # ==================================================
        # SAFETY
        # ==================================================

        rug_risk_score = float(
            token.rug_score
        )

        safety_score = round(
            100
            - rug_risk_score,
            2,
        )

        # ==================================================
        # SOCIAL / WEB PRESENCE
        # ==================================================

        profile = db.scalar(
            select(TokenProfile)
            .where(
                TokenProfile.token_address
                == token.address
            )
        )

        if profile is not None:
            popularity = (
                analyze_popularity(
                    profile
                )
            )

            popularity_score = (
                popularity.score
            )

            popularity_level = (
                popularity.level
            )

            popularity_status = (
                "MEASURED"
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
            popularity_score = None

            popularity_level = (
                "UNKNOWN"
            )

            popularity_status = (
                "UNKNOWN"
            )

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

        popularity_filter_score = (
            popularity_score
            if popularity_score
            is not None
            else 0
        )

        if (
            popularity_filter_score
            < min_popularity
        ):
            continue

        # ==================================================
        # ATTENTION ACCELERATION
        # ==================================================

        attention = analyze_attention(
            db,
            token.address,
        )

        if (
            attention.history_status
            == "NO_DATA"
        ):
            attention_score = None

            organic_attention_score = (
                None
            )

            attention_level = (
                "UNKNOWN"
            )

            attention_status = (
                "UNKNOWN"
            )

        else:
            attention_score = (
                attention.score
            )

            organic_attention_score = (
                attention.organic_score
            )

            attention_level = (
                attention.level
            )

            attention_status = (
                attention.history_status
            )

        attention_filter_score = (
            organic_attention_score
            if organic_attention_score
            is not None
            else 0
        )

        if (
            attention_filter_score
            < min_attention
        ):
            continue

        # ==================================================
        # PROMOTION INFORMATION
        # ==================================================

        promotion_level = (
            attention.promotion_level
        )

        promotion_penalty = (
            attention.metrics.get(
                "promotion_penalty"
            )
            if attention.metrics
            else None
        )

        active_boosts = (
            attention.metrics.get(
                "active_boosts"
            )
            if attention.metrics
            else None
        )

        is_latest_boosted = (
            attention.metrics.get(
                "is_latest_boosted"
            )
            if attention.metrics
            else None
        )

        is_top_boosted = (
            attention.metrics.get(
                "is_top_boosted"
            )
            if attention.metrics
            else None
        )

        # ==================================================
        # BASE OPPORTUNITY SCORE
        # ==================================================
        #
        # Safety             40%
        # Momentum           25%
        # Organic Attention  25%
        # Social Presence    10%
        # ==================================================

        components = [
            {
                "name":
                    "safety",

                "score":
                    safety_score,

                "weight":
                    0.40,

                "available":
                    True,
            },

            {
                "name":
                    "momentum",

                "score":
                    momentum.score,

                "weight":
                    0.25,

                "available":
                    True,
            },

            {
                "name":
                    "attention",

                "score":
                    organic_attention_score,

                "weight":
                    0.25,

                "available":
                    organic_attention_score
                    is not None,
            },

            {
                "name":
                    "popularity",

                "score":
                    popularity_score,

                "weight":
                    0.10,

                "available":
                    popularity_score
                    is not None,
            },
        ]

        available_components = [
            component
            for component
            in components
            if component["available"]
        ]

        available_weight = sum(
            component["weight"]
            for component
            in available_components
        )

        weighted_total = sum(
            (
                component["score"]
                * component["weight"]
            )
            for component
            in available_components
        )

        if available_weight > 0:
            normalized_score = (
                weighted_total
                / available_weight
            )

        else:
            normalized_score = 0

        # --------------------------------------------------
        # DATA COVERAGE
        # --------------------------------------------------

        data_coverage = round(
            available_weight,
            2,
        )

        confidence_factor = (
            0.75
            + (
                0.25
                * data_coverage
            )
        )

        base_opportunity_score = round(
            normalized_score
            * confidence_factor,
            2,
        )

        # ==================================================
        # ENTRY-QUALITY ADJUSTMENTS
        # ==================================================

        adjustment = (
            analyze_opportunity_adjustments(
                promotion_level=
                    promotion_level,

                active_boosts=
                    active_boosts,

                price_change_5m=
                    best_pair.price_change_5m,

                price_change_1h=
                    best_pair.price_change_1h,

                price_change_24h=
                    best_pair.price_change_24h,

                buy_ratio_percent=
                    buy_ratio,

                attention_history=
                    attention_status,

                attention_metrics=
                    attention.metrics,
            )
        )

        opportunity_score = round(
            max(
                0,
                (
                    base_opportunity_score
                    - adjustment.penalty
                ),
            ),
            2,
        )

        if (
            opportunity_score
            < min_opportunity
        ):
            continue

        # ==================================================
        # DATA CONFIDENCE
        # ==================================================

        if (
            data_coverage >= 1.0
            and
            attention.history_status
            in {
                "FULL",
                "PARTIAL",
            }
            and
            market_data_status
            == "LIVE"
        ):
            data_confidence = (
                "HIGH"
            )

        elif (
            data_coverage >= 0.75
            and
            market_data_status
            == "LIVE"
        ):
            data_confidence = (
                "MEDIUM"
            )

        else:
            data_confidence = (
                "LOW"
            )

        # ==================================================
        # OPPORTUNITY LEVEL
        # ==================================================

        if (
            opportunity_score
            >= 80
        ):
            opportunity_level = (
                "HIGH"
            )

        elif (
            opportunity_score
            >= 65
        ):
            opportunity_level = (
                "PROMISING"
            )

        elif (
            opportunity_score
            >= 50
        ):
            opportunity_level = (
                "WATCH"
            )

        else:
            opportunity_level = (
                "WEAK"
            )

        # ==================================================
        # ENTRY QUALITY
        # ==================================================

        if (
            adjustment.level
            == "NONE"
        ):
            entry_quality = (
                "CLEAN"
            )

        elif (
            adjustment.level
            == "LOW"
        ):
            entry_quality = (
                "ACCEPTABLE"
            )

        elif (
            adjustment.level
            == "MODERATE"
        ):
            entry_quality = (
                "CAUTION"
            )

        elif (
            adjustment.level
            == "HIGH"
        ):
            entry_quality = (
                "POOR"
            )

        else:
            entry_quality = (
                "AVOID_CHASING"
            )

        # ==================================================
        # FULL RESULT
        # ==================================================

        results.append({
            # ----------------------------------------------
            # TOKEN
            # ----------------------------------------------

            "symbol":
                token.symbol,

            "name":
                token.name,

            "token_address":
                token.address,

            # ----------------------------------------------
            # FRESHNESS
            # ----------------------------------------------

            "market_data_status":
                market_data_status,

            "market_data_age_minutes":
                market_data_age_minutes,

            "last_refreshed_at":
                best_pair.last_refreshed_at,

            # ----------------------------------------------
            # SAFETY
            # ----------------------------------------------

            "rug_risk_score":
                rug_risk_score,

            "safety_score":
                safety_score,

            # ----------------------------------------------
            # MOMENTUM
            # ----------------------------------------------

            "momentum_score":
                momentum.score,

            "momentum_level":
                momentum.level,

            # ----------------------------------------------
            # SOCIAL PRESENCE
            # ----------------------------------------------

            "popularity_score":
                popularity_score,

            "popularity_level":
                popularity_level,

            "popularity_status":
                popularity_status,

            # ----------------------------------------------
            # ATTENTION
            # ----------------------------------------------

            "attention_score":
                attention_score,

            "organic_attention_score":
                organic_attention_score,

            "attention_level":
                attention_level,

            "attention_history":
                attention_status,

            # ----------------------------------------------
            # PROMOTION
            # ----------------------------------------------

            "promotion_level":
                promotion_level,

            "promotion_penalty":
                promotion_penalty,

            "active_boosts":
                active_boosts,

            "is_latest_boosted":
                is_latest_boosted,

            "is_top_boosted":
                is_top_boosted,

            # ----------------------------------------------
            # OPPORTUNITY
            # ----------------------------------------------

            "base_opportunity_score":
                base_opportunity_score,

            "opportunity_penalty":
                adjustment.penalty,

            "opportunity_score":
                opportunity_score,

            "opportunity_level":
                opportunity_level,

            "entry_quality":
                entry_quality,

            "adjustment_level":
                adjustment.level,

            "adjustment_components":
                adjustment.components,

            "adjustment_warnings":
                adjustment.warnings,

            # ----------------------------------------------
            # DATA QUALITY
            # ----------------------------------------------

            "data_confidence":
                data_confidence,

            "data_coverage":
                data_coverage,

            # ----------------------------------------------
            # MARKET
            # ----------------------------------------------

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

            # ----------------------------------------------
            # PAIR
            # ----------------------------------------------

            "dex":
                best_pair.dex_id,

            "pair_address":
                best_pair.pair_address,

            "pair_created_at":
                best_pair.pair_created_at,

            "discovered_at":
                best_pair.discovered_at,

            # ----------------------------------------------
            # SOCIAL URLS
            # ----------------------------------------------

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

            # ----------------------------------------------
            # EXPLANATIONS
            # ----------------------------------------------

            "momentum_signals":
                momentum.signals,

            "momentum_warnings":
                momentum.warnings,

            "popularity_signals":
                popularity_signals,

            "popularity_warnings":
                popularity_warnings,

            "attention_signals":
                attention.signals,

            "attention_warnings":
                attention.warnings,

            "attention_metrics":
                attention.metrics,
        })

    # ======================================================
    # SORT
    # ======================================================

    results.sort(
        key=lambda item:
            item["opportunity_score"],
        reverse=True,
    )

    results = results[
        :limit
    ]

    # ======================================================
    # RESPONSE
    # ======================================================

    return {
        "status":
            "success",

        "filters": {
            "max_risk":
                max_risk,

            "min_liquidity":
                min_liquidity,

            "min_momentum":
                min_momentum,

            "min_popularity":
                min_popularity,

            "min_attention":
                min_attention,

            "min_opportunity":
                min_opportunity,

            "max_data_age_minutes":
                effective_max_age,

            "include_stale":
                include_stale,

            "limit":
                limit,
        },

        "freshness": {
            "stale_tokens_skipped":
                stale_tokens_skipped,

            "live_data_required":
                not include_stale,
        },

        "count":
            len(results),

        "scoring": {
            "safety_weight":
                0.40,

            "momentum_weight":
                0.25,

            "organic_attention_weight":
                0.25,

            "social_presence_weight":
                0.10,

            "entry_adjustment_enabled":
                True,

            "max_entry_penalty":
                30,

            "paid_promotion_rewarded":
                False,

            "stale_market_data_rewarded":
                False,

            "missing_data":
                (
                    "normalized_with_"
                    "confidence_adjustment"
                ),
        },

        "watchlist":
            results,
    }


# ==========================================================
# COMPACT WATCHLIST
# ==========================================================


@app.get("/watchlist/compact")
def watchlist_compact(
    max_risk: float = 25,
    min_liquidity: float = 5000,
    min_momentum: int = 20,
    min_popularity: int = 0,
    min_attention: int = 0,
    min_opportunity: float = 0,
    max_data_age_minutes: int = 5,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """
    Compact live opportunity view.

    This endpoint uses the exact same ranking engine as
    /watchlist, but returns only the most useful fields.
    """

    full_result = watchlist(
        max_risk=max_risk,
        min_liquidity=min_liquidity,
        min_momentum=min_momentum,
        min_popularity=min_popularity,
        min_attention=min_attention,
        min_opportunity=min_opportunity,
        max_data_age_minutes=
            max_data_age_minutes,
        include_stale=False,
        limit=limit,
        db=db,
    )

    compact = []

    for item in full_result[
        "watchlist"
    ]:
        compact.append({
            "symbol":
                item["symbol"],

            "name":
                item["name"],

            "token_address":
                item["token_address"],

            # ------------------------------------------
            # FINAL RANKING
            # ------------------------------------------

            "opportunity_score":
                item["opportunity_score"],

            "opportunity_level":
                item["opportunity_level"],

            "base_opportunity_score":
                item[
                    "base_opportunity_score"
                ],

            "opportunity_penalty":
                item[
                    "opportunity_penalty"
                ],

            "entry_quality":
                item["entry_quality"],

            # ------------------------------------------
            # CORE SCORES
            # ------------------------------------------

            "safety_score":
                item["safety_score"],

            "momentum_score":
                item["momentum_score"],

            "organic_attention_score":
                item[
                    "organic_attention_score"
                ],

            "attention_level":
                item["attention_level"],

            "attention_history":
                item["attention_history"],

            "popularity_score":
                item["popularity_score"],

            # ------------------------------------------
            # PROMOTION
            # ------------------------------------------

            "promotion_level":
                item["promotion_level"],

            "active_boosts":
                item["active_boosts"],

            # ------------------------------------------
            # MARKET
            # ------------------------------------------

            "liquidity_usd":
                item["liquidity_usd"],

            "volume_24h":
                item["volume_24h"],

            "buy_ratio_percent":
                item[
                    "buy_ratio_percent"
                ],

            "price_change_5m":
                item[
                    "price_change_5m"
                ],

            "price_change_1h":
                item[
                    "price_change_1h"
                ],

            "price_change_24h":
                item[
                    "price_change_24h"
                ],

            # ------------------------------------------
            # DATA QUALITY
            # ------------------------------------------

            "market_data_status":
                item[
                    "market_data_status"
                ],

            "market_data_age_minutes":
                item[
                    "market_data_age_minutes"
                ],

            "data_confidence":
                item["data_confidence"],
        })

    return {
        "status":
            "success",

        "count":
            len(compact),

        "filters": {
            "max_risk":
                max_risk,

            "min_liquidity":
                min_liquidity,

            "min_momentum":
                min_momentum,

            "min_popularity":
                min_popularity,

            "min_attention":
                min_attention,

            "min_opportunity":
                min_opportunity,

            "max_data_age_minutes":
                max_data_age_minutes,

            "limit":
                limit,
        },

        "watchlist":
            compact,
    }