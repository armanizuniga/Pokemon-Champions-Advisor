# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Pokemon Champions VGC Advisor

A Python tool that provides competitive Pokemon VGC (Video Game Championships) analysis for Pokemon Champions — a doubles format featuring Mega Evolutions unique to the game.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Suggest a moveset for a single Pokemon
python scripts/moveset_suggest.py Garchomp
python scripts/moveset_suggest.py "Mr. Rime"

# Run the eval suite
python scripts/eval_moveset.py
python scripts/eval_moveset.py --no-model-grade   # code grading only

# Rebuild Champions-legal data (base stats, items, Smogon filter)
python scripts/fetch_champions_data.py
python scripts/fetch_champions_data.py --skip-pokemon

# Scrape Champions move pools and abilities per species
python scripts/fetch_champions_moves.py
python scripts/fetch_champions_moves.py --resume

# Ingest transcripts into ChromaDB for RAG
python scripts/ingest_transcripts.py

# Node bridge setup (one-time)
bash scripts/setup_node.sh
```

## Project Direction

Building incrementally toward a full VGC battle advisor following the Anthropic Claude API Coursera course structure. Current phase: turn-by-turn battle analysis.

Completed phases:
1. Single Pokemon moveset suggestion ✅
2. 12-Pokemon team preview — which 4 to bring, lead pair, back pair, opponent gameplan prediction ✅
3. 2v2 field state → turn-by-turn battle analysis ✅

Planned phases:
4. FastAPI backend + React frontend
5. iOS app via React Native

## Architecture

### Scripts (`scripts/`)
- `moveset_suggest.py` — Phase 1 core: takes a species name, loads legal data, queries ChromaDB for relevant player commentary (RAG), asks Claude for a moveset recommendation with XML structured output
- `team_preview.py` — Phase 2 core: takes two teams of 6, loads data + RAG for all 12, runs Claude tool use with damage calc to recommend which 4 to bring, lead pair, back pair, and opponent gameplan prediction
- `battle_advisor.py` — Phase 3 core: takes a structured JSON battle state, pre-computes a full damage matrix (your moves × opponent targets, spread move friendly fire, opponent threats), then asks Claude for turn-by-turn action recommendations with switch considerations
- `generate_ev_templates.py` — Generates `data/champions/ev_templates.json` with 4 EV presets per species (max_offense, max_bulk, trick_room, max_speed) used by the damage calc tool
- `eval_moveset.py` — Eval runner: runs all 15 eval dataset Pokemon through the full pipeline (including RAG), grades with code-based + model-based checks, saves timestamped results for baseline comparison
- `fetch_champions_data.py` — Scrapes Serebii for legal Pokemon + items, fetches base stats from PokeAPI for all species + forms/megas, filters Smogon sets to legal items
- `fetch_champions_moves.py` — Scrapes Champions Pokedex on Serebii for legal move pools and abilities per species in one pass
- `ingest_transcripts.py` — Chunks and embeds transcript `.txt` files into ChromaDB for RAG retrieval
- `setup_node.sh` — One-time setup for the Node.js damage calc bridge

### Node Bridge (`node/`)
- `calc_bridge.js` — Reads a JSON array of calc requests from stdin, runs `@smogon/calc` damage calculations in batch, writes results to stdout. Used by `team_preview.py` via Claude tool use.

### Data (`data/`)
- `champions/moves.json` — Champions-legal moves per species keyed by Serebii slug
- `champions/abilities.json` — Legal abilities per form (base + mega) keyed by slug
- `champions/legal_items.json` — Legal items list with effect descriptions
- `champions/ev_templates.json` — 4 EV presets per species for damage calc tool use (max_offense, max_bulk, trick_room, max_speed)
- `pokeapi/base_stats.json` — Base stats for all legal species + mega/form variants
- `smogon/gen9vgc.json` — Smogon competitive sets filtered to Champions-legal items
- `eval/moveset_eval_dataset.json` — 15 Pokemon test cases with expected grading criteria
- `eval/results/` — Timestamped eval run results (gitignored, re-runnable)
- `transcripts/<youtuber>/` — VGC player video transcripts for RAG (gitignored, personal)
- `battle_states/example.json` — Sample Phase 3 battle state (Garchomp+Incineroar vs Torkoal+Venusaur, Sun active)
- `chromadb/` — Persisted ChromaDB vector store (committed to repo, ~11MB)

## Key Conventions

- `ANTHROPIC_API_KEY` env var — never hardcoded
- All Claude calls use `claude-sonnet-4-6` unless noted
- XML structured output for all Claude responses — parse with `re.search` on tag names
- Data files keyed by lowercase slug (`venusaur`, `charizard-mega-x`)
- ChromaDB collection name: `vgc_transcripts`, embedding model: `all-MiniLM-L6-v2`
- Eval results are timestamped JSON in `data/eval/results/` for baseline comparison

## Pokemon Champions Format Notes

- Level 50 doubles (2v2), players bring 4 of 6
- Mega Evolutions are Champions-exclusive and widely available
- **No Life Orb, Choice Band, Assault Vest, or Rocky Helmet** — item pool is different from standard VGC
- Items are mostly: Mega Stones, type-boosting items, berries, Focus Sash, Leftovers, Choice Scarf
- **Affinity Tickets are not held items** — they are collectibles and have been removed from `legal_items.json`
- Incineroar does **not** have Knock Off in Champions (lost in this format)
- Legal Pokemon, moves, and items sourced from Serebii Champions pages

## Data Slugs

Species slugs follow PokeAPI convention: `venusaur`, `charizard-mega-x`, `charizard-mega-y`.
Serebii slugs for move/ability lookups follow Serebii URL convention: `venusaur`, `mr.rime`.
The `name_to_slug()` helper in `moveset_suggest.py` handles the conversion.