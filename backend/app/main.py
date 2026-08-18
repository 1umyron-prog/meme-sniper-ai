from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.analyzers.rug_analyzer import analyze_pair
from backend.app.analyzers.candidate_scorer import score_candidates
from backend.app.db.database import engine, get_db
from backend.app.db.init_db import init_db
from backend.app.scanners.dexscreener import search_tokens
from backend.app.services.token_service import save_pair


app = FastAPI(
    title="MemeSniper AI",
    description="AI-powered meme coin risk and momentum scanner",
    version="0.1.0",
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {
        "name": "MemeSniper AI",
        "status": "online",
        "version": "0.1.0",
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
