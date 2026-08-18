import asyncio

from sqlalchemy import select

from backend.app.analyzers.safety_engine import analyze_token_safety
from backend.app.db.database import SessionLocal
from backend.app.models.pair import Pair
from backend.app.models.token import Token
from backend.app.scanners.discovery import (
    discover_solana_tokens,
    fetch_token_pairs,
)
from backend.app.services.token_service import save_pair


SCAN_INTERVAL_SECONDS = 60
MAX_TOKENS_PER_CYCLE = 20

# On-chain safety analysis requires several Helius requests.
# Keep this conservative while developing.
MAX_SAFETY_ANALYSES_PER_CYCLE = 5


def choose_best_pair(pairs: list[dict]) -> dict | None:
    """
    Choose the most useful pool for market-risk analysis.

    Prefer the pair with the highest reported USD liquidity.
    """

    if not pairs:
        return None

    def liquidity(pair: dict) -> float:
        value = (pair.get("liquidity") or {}).get("usd")

        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    return max(pairs, key=liquidity)


async def run_scan_cycle():
    print(
        "Discovering recent Solana tokens...",
        flush=True,
    )

    discovered = await discover_solana_tokens()

    print(
        f"Discovery feed returned {len(discovered)} Solana tokens",
        flush=True,
    )

    db = SessionLocal()

    tokens_checked = 0
    new_pairs = 0
    existing_pairs = 0
    safety_analyzed = 0
    low_risk = 0
    errors = 0

    try:
        for token_profile in discovered[:MAX_TOKENS_PER_CYCLE]:
            token_address = token_profile["token_address"]

            try:
                pairs = await fetch_token_pairs(
                    token_address
                )

                tokens_checked += 1

                if not pairs:
                    continue

                token_is_new = False

                for pair_data in pairs:
                    pair_address = pair_data.get(
                        "pairAddress"
                    )

                    if not pair_address:
                        continue

                    existing_pair = db.scalar(
                        select(Pair).where(
                            Pair.pair_address
                            == pair_address
                        )
                    )

                    if existing_pair:
                        existing_pairs += 1
                        continue

                    save_pair(
                        db,
                        pair_data,
                    )

                    new_pairs += 1
                    token_is_new = True

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

                # Only spend Helius requests on newly
                # discovered candidates during this cycle.
                if (
                    token_is_new
                    and safety_analyzed
                    < MAX_SAFETY_ANALYSES_PER_CYCLE
                ):
                    best_pair = choose_best_pair(pairs)

                    if best_pair is None:
                        continue

                    try:
                        safety = await analyze_token_safety(
                            token_address,
                            best_pair,
                        )

                        safety_analyzed += 1

                        risk_score = safety[
                            "rug_risk_score"
                        ]

                        risk_level = safety[
                            "rug_risk_level"
                        ]

                        token_record = db.scalar(
                            select(Token).where(
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
                                "SAFETY:"
                                f" {token_address}"
                                f" | risk={risk_score}"
                                f" | level={risk_level}"
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
                                "Safety analysis error "
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
                        f"Token scan error "
                        f"{token_address}: {error}"
                    ),
                    flush=True,
                )

    finally:
        db.close()

    print(
        (
            "SCAN COMPLETE | "
            f"tokens={tokens_checked} | "
            f"new_pairs={new_pairs} | "
            f"existing_pairs={existing_pairs} | "
            f"safety_analyzed={safety_analyzed} | "
            f"low_risk={low_risk} | "
            f"errors={errors}"
        ),
        flush=True,
    )


async def scanner_loop():
    while True:
        try:
            await run_scan_cycle()

        except Exception as error:
            print(
                f"Discovery cycle failed: {error}",
                flush=True,
            )

        print(
            f"Sleeping {SCAN_INTERVAL_SECONDS} seconds...",
            flush=True,
        )

        await asyncio.sleep(
            SCAN_INTERVAL_SECONDS
        )


if __name__ == "__main__":
    asyncio.run(scanner_loop())