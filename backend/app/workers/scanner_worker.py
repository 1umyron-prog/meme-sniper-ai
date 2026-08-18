import asyncio

from sqlalchemy import select

from backend.app.db.database import SessionLocal
from backend.app.models.pair import Pair
from backend.app.scanners.discovery import (
    discover_solana_tokens,
    fetch_token_pairs,
)
from backend.app.services.token_service import save_pair


SCAN_INTERVAL_SECONDS = 60
MAX_TOKENS_PER_CYCLE = 20


async def run_scan_cycle():
    print("Discovering recent Solana tokens...", flush=True)

    discovered = await discover_solana_tokens()

    print(
        f"Discovery feed returned {len(discovered)} Solana tokens",
        flush=True,
    )

    db = SessionLocal()

    tokens_checked = 0
    new_pairs = 0
    existing_pairs = 0
    errors = 0

    try:
        for token in discovered[:MAX_TOKENS_PER_CYCLE]:
            token_address = token["token_address"]

            try:
                pairs = await fetch_token_pairs(token_address)

                tokens_checked += 1

                for pair_data in pairs:
                    pair_address = pair_data.get("pairAddress")

                    if not pair_address:
                        continue

                    existing = db.scalar(
                        select(Pair).where(
                            Pair.pair_address == pair_address
                        )
                    )

                    if existing:
                        existing_pairs += 1
                        continue

                    save_pair(db, pair_data)
                    new_pairs += 1

                    base_token = pair_data.get("baseToken") or {}

                    print(
                        "NEW PAIR:",
                        base_token.get("symbol"),
                        token_address,
                        pair_data.get("dexId"),
                        flush=True,
                    )

            except Exception as error:
                db.rollback()
                errors += 1

                print(
                    f"Token scan error {token_address}: {error}",
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

        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(scanner_loop())