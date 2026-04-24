"""
Rebuild Champions-legal base stats and item data.

Stages:
  1. Scrape Serebii for the legal Pokemon list
  2. For each species, fetch base stats + all forms/megas from PokeAPI
  3. Overwrite data/pokeapi/base_stats.json
  4. Scrape Serebii for the legal items list
  5. Write data/champions/legal_items.json
  6. Filter data/smogon/gen9vgc.json to remove sets with illegal items

Usage:
    python scripts/fetch_champions_data.py
    python scripts/fetch_champions_data.py --skip-pokemon   # skip PokeAPI, only do items + filter
"""

import json
import time
from pathlib import Path

import click
import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import track

console = Console()

SEREBII_POKEMON_URL = "https://www.serebii.net/pokemonchampions/pokemon.shtml"
SEREBII_ITEMS_URL   = "https://www.serebii.net/pokemonchampions/items.shtml"
POKEAPI_BASE        = "https://pokeapi.co/api/v2"

_ROOT            = Path(__file__).parents[1]
BASE_STATS_PATH  = _ROOT / "data/pokeapi/base_stats.json"
LEGAL_ITEMS_PATH = _ROOT / "data/champions/legal_items.json"
SMOGON_PATH      = _ROOT / "data/smogon/gen9vgc.json"

STAT_MAP = {
    "hp": "hp",
    "attack": "atk",
    "defense": "def",
    "special-attack": "spa",
    "special-defense": "spd",
    "speed": "spe",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (vgc-advisor educational project)"}


# ── Serebii scraping ──────────────────────────────────────────────────────────

def scrape_legal_pokemon(client: httpx.Client) -> list[str]:
    """
    Returns a sorted list of unique base species slugs from the Champions Pokemon page.
    Mega prefix is stripped — we resolve forms via PokeAPI varieties instead.
    """
    console.print("[dim]Fetching Serebii legal Pokemon list...[/dim]")
    resp = client.get(SEREBII_POKEMON_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # The second .tab table is the Pokemon list (first is a description blurb)
    tables = soup.find_all("table", class_="tab")
    if len(tables) < 2:
        raise RuntimeError("Could not find Pokemon table on Serebii page")
    table = tables[1]

    base_slugs: set[str] = set()
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        name = cells[3].get_text(strip=True)
        if not name:
            continue
        # Strip "Mega " prefix — we resolve mega variants via PokeAPI varieties
        base_name = name.removeprefix("Mega ").strip()
        slug = _name_to_slug(base_name)
        base_slugs.add(slug)

    slugs = sorted(base_slugs)
    console.print(f"  Found [bold]{len(slugs)}[/bold] unique base species")
    return slugs


def scrape_legal_items(client: httpx.Client) -> list[dict]:
    """Returns list of {name, effect} from the Champions items page."""
    console.print("[dim]Fetching Serebii legal items list...[/dim]")
    resp = client.get(SEREBII_ITEMS_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    seen: set[str] = set()

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            name_tag = cells[1].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if not name or name in seen:
                continue
            seen.add(name)
            effect = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            items.append({"name": name, "effect": effect})

    console.print(f"  Found [bold]{len(items)}[/bold] legal items")
    return items


# ── PokeAPI helpers ───────────────────────────────────────────────────────────

def _name_to_slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace(".", "").replace("'", "")


def _fetch_json(url: str, client: httpx.Client) -> dict | None:
    resp = client.get(url, headers=HEADERS)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def fetch_stats(slug: str, client: httpx.Client) -> dict | None:
    data = _fetch_json(f"{POKEAPI_BASE}/pokemon/{slug}", client)
    if not data:
        return None
    return {
        STAT_MAP[s["stat"]["name"]]: s["base_stat"]
        for s in data["stats"]
        if s["stat"]["name"] in STAT_MAP
    }


def fetch_all_variety_slugs(species_slug: str, client: httpx.Client) -> list[str]:
    """Returns all variant slugs for a species (base + megas + regional forms etc.)"""
    data = _fetch_json(f"{POKEAPI_BASE}/pokemon-species/{species_slug}", client)
    if not data:
        return [species_slug]
    varieties = [v["pokemon"]["name"] for v in data.get("varieties", [])]
    return varieties or [species_slug]


# ── Core fetch ────────────────────────────────────────────────────────────────

def build_base_stats(species_slugs: list[str], client: httpx.Client) -> dict[str, dict]:
    results: dict[str, dict] = {}
    failed: list[str] = []

    for slug in track(species_slugs, description="Fetching species varieties..."):
        # Get all forms/megas for this species
        varieties = fetch_all_variety_slugs(slug, client)
        time.sleep(0.25)

        for variant in varieties:
            stats = fetch_stats(variant, client)
            time.sleep(0.2)
            if stats:
                results[variant] = stats
            else:
                # Only log failures for non-obvious missing variants
                if variant == slug:
                    failed.append(variant)

    if failed:
        console.print(f"\n[yellow]Could not fetch {len(failed)} species:[/yellow]")
        for f in failed:
            console.print(f"  - {f}")

    return results


# ── Smogon filtering ──────────────────────────────────────────────────────────

def filter_smogon_sets(legal_item_names: set[str]) -> tuple[int, int]:
    if not SMOGON_PATH.exists():
        console.print("[yellow]gen9vgc.json not found, skipping filter[/yellow]")
        return 0, 0

    data: dict[str, list[dict]] = json.loads(SMOGON_PATH.read_text())
    legal_lower = {n.lower() for n in legal_item_names} | {""}

    sets_before = sum(len(v) for v in data.values())
    filtered = {
        species: [s for s in sets if (s.get("item") or "").lower() in legal_lower]
        for species, sets in data.items()
    }
    filtered = {k: v for k, v in filtered.items() if v}
    sets_after = sum(len(v) for v in filtered.values())

    SMOGON_PATH.write_text(json.dumps(filtered, indent=2))
    return sets_before, sets_after


# ── Main ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--skip-pokemon", is_flag=True, help="Skip PokeAPI fetching — only do items + Smogon filter")
def main(skip_pokemon: bool) -> None:
    Path("data/pokeapi").mkdir(parents=True, exist_ok=True)
    Path("data/champions").mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=15) as client:

        # ── Stage 1: Scrape legal Pokemon ─────────────────────────────────────
        species_slugs = scrape_legal_pokemon(client)

        # ── Stage 2 & 3: Fetch stats + write base_stats.json ─────────────────
        if not skip_pokemon:
            console.print(f"\n[bold]Fetching base stats from PokeAPI for {len(species_slugs)} species...[/bold]")
            stats = build_base_stats(species_slugs, client)
            BASE_STATS_PATH.write_text(json.dumps(stats, indent=2))
            console.print(f"[green]Saved {len(stats)} entries →[/green] {BASE_STATS_PATH}")
        else:
            console.print("[dim]--skip-pokemon: skipping PokeAPI fetch[/dim]")

        # ── Stage 4 & 5: Scrape + save legal items ───────────────────────────
        item_entries = scrape_legal_items(client)
        legal_item_names = {e["name"] for e in item_entries}
        LEGAL_ITEMS_PATH.write_text(json.dumps(
            {"items": item_entries, "names": sorted(legal_item_names)}, indent=2
        ))
        console.print(f"[green]Saved {len(item_entries)} legal items →[/green] {LEGAL_ITEMS_PATH}")

        # ── Stage 6: Filter Smogon sets ───────────────────────────────────────
        console.print("\n[bold]Filtering Smogon sets...[/bold]")
        before, after = filter_smogon_sets(legal_item_names)
        console.print(
            f"[green]Smogon sets:[/green] {before} → {after} "
            f"([yellow]{before - after} removed[/yellow] with illegal items)"
        )

    console.print("\n[bold green]Done.[/bold green]")


if __name__ == "__main__":
    main()