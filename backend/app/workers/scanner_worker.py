import asyncio

from sqlalchemy import func, select

from backend.app.analyzers.safety_engine import analyze_token_safety
from backend.app.db.database import SessionLocal
from backend.app.models.pair import Pair
from backend.app.models.token import Token
from backend.app.models.token_profile import TokenProfile
from backend.app.scanners.discovery import (
    discover_solana_tokens,
    fetch_token_pairs,
)
from backend.app.services.attention_service import (
    fetch_promotion_context,
    save_attention_snapshot,
)
from backend.app.services.profile_service import save_token_profile
from backend.app.services.token_service import save_pair


SCAN_INTERVAL_SECONDS = 60

MAX_TOKENS_PER_CYCLE = 20
MAX_SAFETY_ANALYSES_PER_CYCLE = 5

# Existing candidates to continuously monitor.
MAX_MONITORED_TOKENS = 75
MONITORED_MAX_RISK = 25
MONITORED_MIN_LIQUIDITY = 5000


def choose_best_pair(pairs: list[dict]) -> dict | None:
    if not pairs:
        return None

    def liquidity(pair: dict) -> float:
        value = (
            pair.get("liquidity")
            or {}
        ).get("usd")

        try:
            return float(value or 0)

        except (TypeError, ValueError):
            return 0.0

    return max(
        pairs,
        key=liquidity,
    )


def promotion_fallback() -> dict:
    return {
        "latest_boosts": {},
        "top_boosted": set(),
        "community_takeovers": set(),

        "latest_boosts_available": False,
        "top_boosts_available": False,
        "community_takeovers_available": False,

        "errors": [],
    }


def save_current_pairs(
    db,
    token_address: str,
    pairs: list[dict],
) -> tuple[int, int]:
    new_pairs = 0
    refreshed_pairs = 0

    for pair_data in pairs:
        pair_address = pair_data.get(
            "pairAddress"
        )

        if not pair_address:
            continue

        existing_pair = db.scalar(
            select(Pair)
            .where(
                Pair.pair_address
                == pair_address
            )
        )

        was_existing = (
            existing_pair is not None
        )

        save_pair(
            db,
            pair_data,
        )

        if was_existing:
            refreshed_pairs += 1

        else:
            new_pairs += 1

            base_token = (
                pair_data.get("baseToken")
                or {}
            )

            print(
                "NEW PAIR:",
                base_token.get("symbol"),
                token_address,
                pair_data.get("dexId"),
                flush=True,
            )

    return (
        new_pairs,
        refreshed_pairs,
    )


def save_current_attention(
    db,
    token_address: str,
    best_pair: dict,
    promotion_context: dict,
):
    profile = db.scalar(
        select(TokenProfile)
        .where(
            TokenProfile.token_address
            == token_address
        )
    )

    snapshot = save_attention_snapshot(
        db=db,
        token_address=token_address,
        pair_data=best_pair,
        profile=profile,
        promotion_context=promotion_context,
    )

    if (
        snapshot.active_boosts
        or snapshot.is_latest_boosted
        or snapshot.is_top_boosted
    ):
        print(
            (
                f"PROMOTION: {token_address}"
                f" | active_boosts="
                f"{snapshot.active_boosts}"
                f" | latest="
                f"{snapshot.is_latest_boosted}"
                f" | top="
                f"{snapshot.is_top_boosted}"
                f" | amount="
                f"{snapshot.latest_boost_amount}"
                f" | total="
                f"{snapshot.total_boost_amount}"
            ),
            flush=True,
        )

    return snapshot


async def run_scan_cycle():
    print(
        "Discovering recent Solana tokens...",
        flush=True,
    )

    # ==================================================
    # PROMOTION DATA
    # ==================================================

    try:
        promotion_context = (
            await fetch_promotion_context()
        )

        for warning in (
            promotion_context.get("errors")
            or []
        ):
            print(
                f"Promotion feed warning: {warning}",
                flush=True,
            )

    except Exception as error:
        print(
            f"Promotion context error: {error}",
            flush=True,
        )

        promotion_context = (
            promotion_fallback()
        )

    # ==================================================
    # NEW TOKEN DISCOVERY
    # ==================================================

    discovered = (
        await discover_solana_tokens()
    )

    print(
        (
            f"Discovery feed returned "
            f"{len(discovered)} Solana tokens"
        ),
        flush=True,
    )

    db = SessionLocal()

    discovery_tokens = 0
    monitored_tokens = 0

    profiles_saved = 0

    new_pairs = 0
    refreshed_pairs = 0

    attention_snapshots = 0

    safety_analyzed = 0
    low_risk = 0

    errors = 0

    snapshotted_addresses = set()

    try:
        # ==================================================
        # PASS 1
        # NEW / RECENT TOKENS
        # ==================================================

        for token_profile in discovered[
            :MAX_TOKENS_PER_CYCLE
        ]:
            token_address = token_profile[
                "token_address"
            ]

            discovery_tokens += 1

            # ------------------------------------------
            # PROFILE
            # ------------------------------------------

            try:
                save_token_profile(
                    db,
                    token_profile,
                )

                profiles_saved += 1

            except Exception as error:
                db.rollback()
                errors += 1

                print(
                    (
                        f"Profile save error "
                        f"{token_address}: "
                        f"{error}"
                    ),
                    flush=True,
                )

            try:
                # --------------------------------------
                # SAFETY STATUS
                # --------------------------------------

                token_before_scan = db.scalar(
                    select(Token)
                    .where(
                        Token.address
                        == token_address
                    )
                )

                needs_safety_analysis = (
                    token_before_scan is None
                    or token_before_scan.rug_score
                    is None
                )

                # --------------------------------------
                # LIVE PAIRS
                # --------------------------------------

                pairs = await fetch_token_pairs(
                    token_address
                )

                if not pairs:
                    continue

                created, refreshed = (
                    save_current_pairs(
                        db,
                        token_address,
                        pairs,
                    )
                )

                new_pairs += created
                refreshed_pairs += refreshed

                best_pair = choose_best_pair(
                    pairs
                )

                if best_pair is None:
                    continue

                # --------------------------------------
                # ATTENTION SNAPSHOT
                # --------------------------------------

                try:
                    save_current_attention(
                        db,
                        token_address,
                        best_pair,
                        promotion_context,
                    )

                    attention_snapshots += 1

                    snapshotted_addresses.add(
                        token_address
                    )

                except Exception as error:
                    db.rollback()
                    errors += 1

                    print(
                        (
                            f"Attention snapshot error "
                            f"{token_address}: "
                            f"{error}"
                        ),
                        flush=True,
                    )

                # --------------------------------------
                # SAFETY ANALYSIS
                # --------------------------------------

                if (
                    needs_safety_analysis
                    and safety_analyzed
                    < MAX_SAFETY_ANALYSES_PER_CYCLE
                ):
                    try:
                        safety = (
                            await analyze_token_safety(
                                token_address,
                                best_pair,
                            )
                        )

                        safety_analyzed += 1

                        risk_score = safety[
                            "rug_risk_score"
                        ]

                        risk_level = safety[
                            "rug_risk_level"
                        ]

                        token_record = db.scalar(
                            select(Token)
                            .where(
                                Token.address
                                == token_address
                            )
                        )

                        if token_record:
                            token_record.rug_score = (
                                risk_score
                            )

                            liquidity = (
                                best_pair.get(
                                    "liquidity"
                                )
                                or {}
                            )

                            try:
                                token_record.liquidity = (
                                    float(
                                        liquidity.get(
                                            "usd"
                                        )
                                        or 0
                                    )
                                )

                            except (
                                TypeError,
                                ValueError,
                            ):
                                pass

                            db.commit()

                        if risk_score <= 25:
                            low_risk += 1

                        print(
                            (
                                f"SAFETY: "
                                f"{token_address}"
                                f" | risk="
                                f"{risk_score}"
                                f" | level="
                                f"{risk_level}"
                                f" | market="
                                f"{safety['components']['market_risk']}"
                                f" | holders="
                                f"{safety['components']['holder_risk']}"
                                f" | authority="
                                f"{safety['components']['authority_risk']}"
                            ),
                            flush=True,
                        )

                    except Exception as error:
                        db.rollback()
                        errors += 1

                        print(
                            (
                                f"Safety analysis error "
                                f"{token_address}: "
                                f"{error}"
                            ),
                            flush=True,
                        )

            except Exception as error:
                db.rollback()
                errors += 1

                print(
                    (
                        f"Discovery token error "
                        f"{token_address}: "
                        f"{error}"
                    ),
                    flush=True,
                )

        # ==================================================
        # PASS 2
        #
        # MONITOR ACTIVE LOW-RISK CANDIDATES
        #
        # IMPORTANT:
        # We prioritize 24h trading volume now instead of
        # simply choosing the highest-liquidity tokens.
        # ==================================================

        monitored_addresses = db.scalars(
            select(Token.address)
            .join(
                Pair,
                Pair.token_address
                == Token.address,
            )
            .where(
                Token.rug_score.is_not(None)
            )
            .where(
                Token.rug_score
                <= MONITORED_MAX_RISK
            )
            .where(
                Pair.liquidity_usd
                >= MONITORED_MIN_LIQUIDITY
            )
            .group_by(
                Token.address
            )
            .order_by(
                func.max(
                    Pair.volume_24h
                ).desc()
            )
            .limit(
                MAX_MONITORED_TOKENS
            )
        ).all()

        for token_address in monitored_addresses:
            # Avoid duplicate snapshot if it was already
            # processed through discovery this cycle.
            if (
                token_address
                in snapshotted_addresses
            ):
                continue

            try:
                pairs = await fetch_token_pairs(
                    token_address
                )

                monitored_tokens += 1

                if not pairs:
                    continue

                created, refreshed = (
                    save_current_pairs(
                        db,
                        token_address,
                        pairs,
                    )
                )

                new_pairs += created
                refreshed_pairs += refreshed

                best_pair = choose_best_pair(
                    pairs
                )

                if best_pair is None:
                    continue

                save_current_attention(
                    db,
                    token_address,
                    best_pair,
                    promotion_context,
                )

                attention_snapshots += 1

                snapshotted_addresses.add(
                    token_address
                )

            except Exception as error:
                db.rollback()
                errors += 1

                print(
                    (
                        f"Monitor error "
                        f"{token_address}: "
                        f"{error}"
                    ),
                    flush=True,
                )

    finally:
        db.close()

    # ==================================================
    # SUMMARY
    # ==================================================

    print(
        (
            "SCAN COMPLETE | "
            f"discovery_tokens="
            f"{discovery_tokens} | "
            f"monitored_tokens="
            f"{monitored_tokens} | "
            f"profiles_saved="
            f"{profiles_saved} | "
            f"new_pairs="
            f"{new_pairs} | "
            f"refreshed_pairs="
            f"{refreshed_pairs} | "
            f"attention_snapshots="
            f"{attention_snapshots} | "
            f"safety_analyzed="
            f"{safety_analyzed} | "
            f"low_risk="
            f"{low_risk} | "
            f"errors="
            f"{errors}"
        ),
        flush=True,
    )


async def scanner_loop():
    while True:
        try:
            await run_scan_cycle()

        except Exception as error:
            print(
                (
                    f"Discovery cycle failed: "
                    f"{error}"
                ),
                flush=True,
            )

        print(
            (
                f"Sleeping "
                f"{SCAN_INTERVAL_SECONDS} "
                f"seconds..."
            ),
            flush=True,
        )

        await asyncio.sleep(
            SCAN_INTERVAL_SECONDS
        )


if __name__ == "__main__":
    asyncio.run(
        scanner_loop()
    )