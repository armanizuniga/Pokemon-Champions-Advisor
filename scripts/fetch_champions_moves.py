"""
Scrape Champions-legal move pools and abilities for every Pokemon from Serebii.

Hits each species page once and extracts both Standard Moves and Abilities in
the same pass. Abilities are stored per form (base + mega) since megas can
have different abilities (e.g. Mega Venusaur gets Thick Fat).

Outputs:
    data/champions/moves.json      { "venusaur": ["Acid Spray", ...], ... }
    data/champions/abilities.json  { "venusaur": ["Overgrow", "Chlorophyll"],
                                     "venusaur-mega": ["Thick Fat"], ... }

Usage:
    python scripts/fetch_champions_moves.py
    python scripts/fetch_champions_moves.py --resume   # skip already-fetched species
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
SEREBII_DEX_URL     = "https://www.serebii.net/pokedex-champions/{slug}/"
_ROOT               = Path(__file__).parents[1]
MOVES_PATH          = _ROOT / "data/champions/moves.json"
ABILITIES_PATH      = _ROOT / "data/champions/abilities.json"
HEADERS             = {"User-Agent": "Mozilla/5.0 (vgc-advisor educational project)"}


def scrape_species_slugs(client: httpx.Client) -> dict[str, str]:
    """
    Returns {display_name: serebii_slug} for all base (non-Mega) species.
    Slugs are pulled from href attributes so edge cases like Mr. Rime (mr.rime)
    are handled correctly.
    """
    resp = client.get(SEREBII_POKEMON_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tables = soup.find_all("table", class_="tab")
    if len(tables) < 2:
        raise RuntimeError("Could not find Pokemon table on Serebii")
    table = tables[1]

    slug_map: dict[str, str] = {}
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        name = cells[3].get_text(strip=True)
        link = cells[3].find("a")
        if not name or name.startswith("Mega ") or not link:
            continue
        href = link.get("href", "")
        slug = href.strip("/").split("/")[-1]
        if slug:
            slug_map[name] = slug

    return slug_map


def _extract_abilities_from_table(table) -> list[str]:
    """Extract ability names from a dextable abilities row."""
    first_row = table.find("tr")
    if not first_row:
        return []
    return [b.get_text(strip=True) for b in first_row.find_all("b") if b.get_text(strip=True) != "Abilities"]


def scrape_page(slug: str, client: httpx.Client) -> tuple[list[str], dict[str, list[str]]] | None:
    """
    Fetches one Champions Pokedex page and returns:
        (moves, abilities_by_form)
    where abilities_by_form maps form slug → ability list.
    Returns None on 404.
    """
    url = SEREBII_DEX_URL.format(slug=slug)
    resp = client.get(url, headers=HEADERS)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    dextables = soup.find_all("table", class_="dextable")

    # ── Moves ────────────────────────────────────────────────────────────────
    moves: list[str] = []
    for table in dextables:
        first_cell = table.find("td")
        if first_cell and "Standard Moves" in first_cell.get_text():
            for row in table.find_all("tr")[2:]:
                cells = row.find_all("td")
                if len(cells) < 3:
                    continue
                move_name = cells[0].get_text(strip=True)
                if move_name:
                    moves.append(move_name)
            break

    # ── Abilities ─────────────────────────────────────────────────────────────
    # There is one abilities dextable per form on the page (base, then mega).
    # We map them positionally: first = base slug, second = mega slug (if any).
    abilities_tables = [
        t for t in dextables
        if (t.find("td") and "Abilities" in t.find("td").get_text())
    ]

    abilities_by_form: dict[str, list[str]] = {}
    form_slugs = [slug]  # base form is always first

    # Check if the page contains a mega section by looking for a mega header table
    for table in dextables:
        first_cell = table.find("td")
        if first_cell:
            text = first_cell.get_text(strip=True)
            if text.startswith("Mega ") and text != "Mega Evolution":
                mega_name = text  # e.g. "Mega Venusaur"
                base_name = mega_name.replace("Mega ", "", 1).strip()
                mega_slug = base_name.lower().replace(" ", "-").replace(".", "").replace("'", "") + "-mega"
                if mega_slug not in form_slugs:
                    form_slugs.append(mega_slug)

    for i, abilities_table in enumerate(abilities_tables):
        form = form_slugs[i] if i < len(form_slugs) else f"{slug}-form{i}"
        abilities_by_form[form] = _extract_abilities_from_table(abilities_table)

    return moves, abilities_by_form


@click.command()
@click.option("--resume", is_flag=True, help="Skip species already present in moves.json")
def main(resume: bool) -> None:
    MOVES_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing_moves: dict[str, list[str]] = {}
    existing_abilities: dict[str, list[str]] = {}

    if resume and MOVES_PATH.exists():
        existing_moves = json.loads(MOVES_PATH.read_text())
        console.print(f"[dim]Resuming moves — {len(existing_moves)} species already fetched[/dim]")
    if resume and ABILITIES_PATH.exists():
        existing_abilities = json.loads(ABILITIES_PATH.read_text())
        console.print(f"[dim]Resuming abilities — {len(existing_abilities)} forms already fetched[/dim]")

    with httpx.Client(timeout=15) as client:
        console.print("[dim]Fetching species list from Serebii...[/dim]")
        slug_map = scrape_species_slugs(client)
        console.print(f"  [bold]{len(slug_map)}[/bold] base species to scrape\n")

        all_moves = dict(existing_moves)
        all_abilities = dict(existing_abilities)
        failed: list[str] = []

        for name, slug in track(slug_map.items(), description="Scraping moves + abilities..."):
            if resume and slug in existing_moves:
                continue

            result = scrape_page(slug, client)
            time.sleep(0.4)

            if result is None:
                console.print(f"  [yellow]404:[/yellow] {name} ({slug})")
                failed.append(name)
                continue

            moves, abilities_by_form = result
            all_moves[slug] = moves
            all_abilities.update(abilities_by_form)

            # Save incrementally so a crash doesn't lose progress
            MOVES_PATH.write_text(json.dumps(all_moves, indent=2))
            ABILITIES_PATH.write_text(json.dumps(all_abilities, indent=2))

    console.print(f"\n[green]Saved {len(all_moves)} species →[/green] {MOVES_PATH}")
    console.print(f"[green]Saved {len(all_abilities)} forms →[/green] {ABILITIES_PATH}")

    if failed:
        console.print(f"[yellow]Failed ({len(failed)}):[/yellow] {', '.join(failed)}")

    total_moves = sum(len(v) for v in all_moves.values())
    avg = total_moves // len(all_moves) if all_moves else 0
    console.print(f"Total moves across all species: [bold]{total_moves}[/bold] (avg {avg} per species)")


if __name__ == "__main__":
    main()