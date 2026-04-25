# Pokémon Champions VGC Advisor

A competitive advisor for **Pokémon Champions** — a doubles VGC format. Built with the Anthropic Claude API.

## What it does

- Recommends competitive movesets, items, abilities, and EV spreads for any legal Pokémon
- Analyzes a full 12-Pokémon team preview (your 6 vs opponent's 6) and recommends which 4 to bring, who to lead, and predicts the opponent's gameplan
- Runs live damage calculations via the Smogon calc to verify KO thresholds before making recommendations
- Pulls expert strategy from top VGC player commentary via RAG retrieval (ChromaDB)
- Validates moveset output with a prompt eval suite — code-based and model-based grading

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Single Pokémon moveset suggestion | ✅ Done |
| 2 | 12-Pokémon team preview → which 4 to bring, lead pair, opponent prediction | ✅ Done |
| 3 | 2v2 field state → turn-by-turn battle analysis | Planned |
| 4 | FastAPI backend + React web app | Planned |
| 5 | React Native iOS app | Planned |

## Setup

**Requirements:** Python 3.11+, Node.js

```bash
# Clone and install
git clone https://github.com/armanizuniga/pokemon-champions-advisor.git
cd pokemon-champions-advisor
pip install -r requirements.txt

# Set your API key
cp .env.example .env
# Edit .env and add your Anthropic API key

# Node bridge (one-time — needed for damage calculations)
bash scripts/setup_node.sh
```

## Usage

```bash
# Suggest a moveset for a single Pokémon
python scripts/moveset_suggest.py Garchomp
python scripts/moveset_suggest.py "Mr. Rime"

# Team preview — your 6 vs opponent's 6
python scripts/team_preview.py \
  "Umbreon,Ceruledge,Altaria,Glimmora,Gallade,Floette" \
  "Cofagrigus,Camerupt,Wyrdeer,Skeledirge,Beartic,Tauros"

# Run the prompt eval suite
python scripts/eval_moveset.py                  # full eval with model and code grading
```

## How it works

**Phase 1 — Moveset suggestion**
```
Pokémon name
     │
     ▼
Load legal data          moves.json + abilities.json + legal_items.json
     │
     ▼
RAG retrieval            ChromaDB → expert commentary chunks for this Pokémon
     │
     ▼
Claude API call          System prompt + data + RAG → XML moveset response
     │
     ▼
Parse + display          Extract XML tags → rich terminal output
```

**Phase 2 — Team preview**
```
Your 6 + Opponent's 6
     │
     ▼
Load legal data          moves + abilities + base stats + EV templates for all 12
     │
     ▼
RAG retrieval            ChromaDB → user team (TOP_K=2) + opponent team (TOP_K=1) + team strategy
     │
     ▼
Claude API call          System prompt + all 12 Pokémon data + RAG context
     │                   Tool: run_damage_calcs (batched)
     ▼
Tool use loop            Claude calls damage calc as needed → calc_bridge.js via Node
     │                   Returns damage calcs results per matchup
     ▼
Final response           XML: bring 4, lead 2, back 2, opponent prediction, contingency
     │
     ▼
Parse + display          Rich terminal panels
```

## Data

All data is pre-built and committed. To rebuild from scratch:

```bash
# Rebuild base stats + legal items
python scripts/fetch_champions_data.py

# Scrape move pools and abilities from Serebii
python scripts/fetch_champions_moves.py
```

| File | Source | Contents |
|------|--------|----------|
| `data/champions/moves.json` | Serebii | Legal moves per Pokémon |
| `data/champions/abilities.json` | Serebii | Legal abilities per form |
| `data/champions/legal_items.json` | Serebii | Legal held items + effects |
| `data/champions/ev_templates.json` | Generated | 4 EV presets per species for damage calc |
| `data/pokeapi/base_stats.json` | PokeAPI | Base stats for all Pokémon + megas |
| `data/smogon/gen9vgc.json` | Smogon | Competitive sets filtered to legal items |
| `data/chromadb/` | Local | ChromaDB vector store (~11MB) |

## Pokémon Champions Format Notes

- Level 50 doubles (2v2), bring 4 of 6 Pokémon
- Mega Evolutions are Champions-exclusive and widely available
- Item pool differs significantly from standard VGC — no Life Orb, Choice Band, or Assault Vest
- Items are primarily Mega Stones, berries, type-boosting items, Focus Sash, Choice Scarf

## Tech Stack

- **Claude API** (`claude-sonnet-4-6`) — moveset generation and model-based eval grading
- **ChromaDB** + `sentence-transformers` — local vector store for RAG
- **@smogon/calc** (Node.js) — damage calculation bridge
- **httpx** + **BeautifulSoup** — Serebii scraping
- **rich** + **click** — terminal UI