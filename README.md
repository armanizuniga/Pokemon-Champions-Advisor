# Pokémon Champions VGC Advisor

A competitive advisor for **Pokémon Champions** — a doubles VGC format. Built with the Anthropic Claude API.

## What it does

- Recommends competitive movesets, items, abilities, and EV spreads for any legal Pokémon
- Recommendations from Champions-legal data (moves, abilities, items)
- Uses RAG retrieval from forums and YouTube videos of top VGC players to inform strategy
- Validates output with a prompt eval suite — code-based and model-based grading — so prompt improvements are measurable

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Single Pokémon moveset suggestion | ✅ Current |
| 2 | Full team of 6 → recommend 4 to bring + lead pair | Planned |
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
# Suggest a moveset for a Pokémon
python scripts/moveset_suggest.py Garchomp
python scripts/moveset_suggest.py "Mr. Rime"

# Run the prompt eval suite
python scripts/eval_moveset.py                  # full eval with model and code grading
```

## How it works

```
Pokémon name
     │
     ▼
Load legal data          champions/moves.json + abilities.json + legal_items.json
     │
     ▼
RAG retrieval            ChromaDB query → relevant chunks from forums and expert knowledge
     │
     ▼
Claude API call          System prompt + Pokémon data + RAG context → XML response
     │
     ▼
Parse + display          Extract XML tags → rich terminal output
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