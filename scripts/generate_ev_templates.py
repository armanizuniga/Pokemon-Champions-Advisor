"""
Generate EV templates for all Pokemon in base_stats.json.

Produces 4 preset spreads per species used by the damage calc tool
during team preview to bound realistic damage ranges.

Usage:
    python scripts/generate_ev_templates.py
"""

import json
from pathlib import Path

DATA           = Path(__file__).parents[1] / "data"
BASE_STATS     = DATA / "pokeapi/base_stats.json"
OUTPUT_PATH    = DATA / "champions/ev_templates.json"


def primary_offense(stats: dict) -> str:
    return "atk" if stats["atk"] >= stats["spa"] else "spa"


def build_templates(stats: dict) -> dict:
    # Champions uses stat points (0-32 per stat, 64 total bank)
    off = primary_offense(stats)

    return {
        "max_offense": {
            "hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 32,
            off: 32,
        },
        "max_bulk": {
            "hp": 32, "atk": 0, "def": 16, "spa": 0, "spd": 16, "spe": 0,
        },
        "trick_room": {
            "hp": 32, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0,
            off: 32,
        },
        "max_speed": {
            "hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 32,
            off: 32,
        },
    }


def main() -> None:
    base_stats = json.loads(BASE_STATS.read_text())

    templates = {
        slug: build_templates(stats)
        for slug, stats in base_stats.items()
    }

    OUTPUT_PATH.write_text(json.dumps(templates, indent=2))
    print(f"Written {len(templates)} Pokemon to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()