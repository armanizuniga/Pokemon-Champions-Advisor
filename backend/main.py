"""
FastAPI backend for the Champions VGC Advisor.

Endpoints:
  POST /api/analyze          — full pipeline: RAG + damage matrix + Claude
  GET  /api/pokemon/{species} — legal moves, abilities, base stats for a species
  GET  /api/items            — full legal items list

Run with:
  uvicorn backend.main:app --reload
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.advisor import load_pokemon_data, load_items, list_pokemon, run_analysis

app = FastAPI(title="Champions VGC Advisor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:4173",  # Vite preview
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── POST /api/analyze ─────────────────────────────────────────────────────────

class BattleState(BaseModel):
    turn: int = 1
    your_active: list[dict]
    opponent_active: list[dict]
    your_back: list[dict] = []
    opponent_back: list[dict] = []
    field: dict = {}

    model_config = {"extra": "allow"}


@app.post("/api/analyze")
async def analyze(state: BattleState):
    try:
        result = run_analysis(state.model_dump())
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


# ── GET /api/pokemon ─────────────────────────────────────────────────────────

@app.get("/api/pokemon")
async def list_pokemon_endpoint():
    return list_pokemon()


# ── GET /api/pokemon/{species} ────────────────────────────────────────────────

@app.get("/api/pokemon/{species}")
async def get_pokemon(species: str):
    data = load_pokemon_data(species)
    if not data["base_stats"]:
        raise HTTPException(status_code=404, detail=f"Species not found: {species}")
    return data


# ── GET /api/items ────────────────────────────────────────────────────────────

@app.get("/api/items")
async def get_items():
    return load_items()


# ── GET /api/health ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}
