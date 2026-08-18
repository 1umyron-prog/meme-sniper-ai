from backend.app.analyzers.solana_safety import helius_rpc


SYSTEM_PROGRAM = "11111111111111111111111111111111"

KNOWN_PROGRAMS = {
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": {
        "name": "PumpSwap AMM",
        "category": "liquidity_pool",
    },
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": {
        "name": "Pump.fun Bonding Curve",
        "category": "bonding_curve",
    },
}


async def classify_owner(owner_address: str) -> dict:
    result = await helius_rpc(
        "getAccountInfo",
        [
            owner_address,
            {
                "encoding": "base64",
            },
        ],
    )

    account = result.get("value")

    if account is None:
        return {
            "address": owner_address,
            "classification": "unknown",
            "protocol": None,
            "account_program": None,
            "executable": False,
            "lamports": 0,
            "reason": "Account not found",
        }

    executable = bool(account.get("executable"))
    account_program = account.get("owner")
    lamports = account.get("lamports", 0)

    if executable:
        classification = "program_account"
        protocol = None
        reason = "Address is an executable Solana program"

    elif account_program == SYSTEM_PROGRAM:
        classification = "ordinary_account"
        protocol = None
        reason = "Address is owned by the System Program"

    elif account_program in KNOWN_PROGRAMS:
        known = KNOWN_PROGRAMS[account_program]

        classification = known["category"]
        protocol = known["name"]

        reason = (
            f"Account is controlled by the known "
            f"{known['name']} program"
        )

    else:
        classification = "program_owned_account"
        protocol = None

        reason = (
            "Address is a non-executable account owned by "
            f"program {account_program}"
        )

    return {
        "address": owner_address,
        "classification": classification,
        "protocol": protocol,
        "account_program": account_program,
        "executable": executable,
        "lamports": lamports,
        "reason": reason,
    }


async def classify_owners(
    owner_addresses: list[str],
) -> list[dict]:
    results = []
    seen = set()

    for owner_address in owner_addresses:
        if not owner_address:
            continue

        if owner_address in seen:
            continue

        seen.add(owner_address)

        result = await classify_owner(owner_address)
        results.append(result)

    return results
