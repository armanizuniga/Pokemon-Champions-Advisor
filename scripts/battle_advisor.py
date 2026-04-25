"""
Phase 3 — Turn-by-turn battle advisor.

Given a structured board state (your 2 active, opponent's 2 active, back Pokémon,
field conditions), pre-computes a full damage matrix and asks Claude for the
best action for each of your Pokémon this turn — move + target or switch out.

Opponent unknown fields (item, ability, moves) default to EV templates.
Update state.json each turn as opponent info is revealed.

Usage:
    python scripts/battle_advisor.py data/battle_states/example.json
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import anthropic
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA              = Path(__file__).parents[1] / "data"
MOVES_PATH        = DATA / "champions/moves.json"
ABILITIES_PATH    = DATA / "champions/abilities.json"
ITEMS_PATH        = DATA / "champions/legal_items.json"
BASE_STATS_PATH   = DATA / "pokeapi/base_stats.json"
EV_TEMPLATES_PATH = DATA / "champions/ev_templates.json"
CHROMADB_PATH     = DATA / "chromadb"
NODE_BRIDGE       = Path(__file__).parents[1] / "node/calc_bridge.js"
RAG_TOP_K         = 2

# ── Spread move classification ────────────────────────────────────────────────
# Moves that hit ALL adjacent Pokémon including partner — friendly fire applies
SPREAD_ALL_ADJACENT = frozenset({
    "earthquake", "magnitude", "surf", "discharge", "lava plume",
    "bulldoze", "explosion", "self-destruct", "sludge wave",
    "mind blown", "misty explosion", "sparkling aria",
})

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an elite Pokémon VGC battle coach specializing in Pokémon Champions — \
a doubles format with Mega Evolutions. You are advising a player mid-battle, \
turn by turn. You have been given the current board state and a pre-computed \
damage matrix for all relevant matchups.

## Your Job This Turn
1. Determine the best action for each of the user's 2 active Pokémon: \
   move + target, or switch to a back Pokémon
2. Identify the priority order — who moves first given Speed tiers, \
   Trick Room, Tailwind, and priority moves
3. Assess what the opponent threatens this turn
4. Provide a contingency if the opponent uses Protect or makes a surprising play

## Decision Framework
- **Check KO windows first**: use the damage matrix to identify if you can take \
  a KO this turn — KOs deny the opponent an action
- **Spread move friendly fire**: if a spread move damages your own partner, \
  evaluate whether it is worth it — sometimes KOing your own Pokémon is correct \
  to get a free switch-in of a better matchup
- **Switch considerations**: switching resets your stat drops (Intimidate stacks), \
  brings in a better type matchup, or saves a key Pokémon. Cost: opponent gets \
  a free turn of damage on the switch-in
- **Protect value**: high when you are threatened, when you need to scout, or \
  when you want to let a Trick Room / Tailwind / weather turn expire
- **Priority order matters**: if you move first you may be able to KO before \
  the opponent acts; if you move second factor in what damage you will take first
- **Consecutive Protect**: only 1/3 chance of success — do not rely on it

## Champions-Specific Rules
- No IVs — EVs and Natures only
- Paralysis: 12.5% immobility chance (not 25%)
- Freeze: guaranteed thaw by turn 3
- Unseen Fist: only 1/4 damage through Protect
- No Flame Orb / Toxic Orb — Guts / Poison Heal strategies are not viable
- Terrain-setting abilities not in game — terrain is move-only
- Priority blockers: Armor Tail (Farigiraf), Queenly Majesty (Tsareena), \
  Psychic Terrain (grounded Pokémon)

## Output Format
Respond using these exact XML tags:

<battle_recommendation>
  <action_1>[Your first Pokémon's action: "Use [Move] on [Target]" or "Switch to [Pokémon]"]</action_1>
  <action_2>[Your second Pokémon's action: "Use [Move] on [Target]" or "Switch to [Pokémon]"]</action_2>
  <priority_order>[Who moves first and why — Speed tiers, TR, tailwind, priority moves]</priority_order>
  <threat_assessment>[What the opponent threatens this turn and how much damage]</threat_assessment>
  <contingency>[If opponent Protects or surprises, what to do differently]</contingency>
  <reasoning>[Full explanation: KO math from the damage matrix, why this action over alternatives, switch logic if applicable, spread move friendly fire rationale if relevant]</reasoning>
</battle_recommendation>
"""

# ── Data loading ───────────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    return name.lower().strip().replace(" ", "-").replace(".", "").replace("'", "")


def load_pokemon_data(species: str) -> dict:
    slug = name_to_slug(species)

    moves_data     = json.loads(MOVES_PATH.read_text())
    abilities_data = json.loads(ABILITIES_PATH.read_text())
    base_stats     = json.loads(BASE_STATS_PATH.read_text())
    ev_templates   = json.loads(EV_TEMPLATES_PATH.read_text())

    moves     = moves_data.get(slug) or moves_data.get(slug.split("-")[0], [])
    abilities = (
        abilities_data.get(slug)
        or abilities_data.get(slug + "-mega")
        or abilities_data.get(slug.split("-")[0], [])
    )
    stats = base_stats.get(slug) or base_stats.get(slug.split("-")[0], {})
    evs   = ev_templates.get(slug) or ev_templates.get(slug.split("-")[0], {})

    return {"species": species, "slug": slug, "moves": moves,
            "abilities": abilities, "base_stats": stats, "ev_templates": evs}


# ── RAG ───────────────────────────────────────────────────────────────────────

_chroma_client = None
_chroma_collections: dict = {}

def _get_client():
    global _chroma_client
    if _chroma_client is None:
        ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        _chroma_client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        _chroma_client._embed_fn = ef
    return _chroma_client

def _get_collection(name: str):
    if name not in _chroma_collections:
        client = _get_client()
        try:
            _chroma_collections[name] = client.get_collection(
                name, embedding_function=client._embed_fn
            )
        except Exception:
            return None
    return _chroma_collections[name]

def _format_chunk(doc: str, meta: dict) -> str:
    if meta.get("source_type") == "web":
        return f"[{meta['site']} — {meta['page_title']}]\n{doc}"
    return f"[{meta.get('youtuber', '?')} — {meta.get('source', '?')}]\n{doc}"

def retrieve_rag_context(species: str) -> list[str]:
    if not CHROMADB_PATH.exists():
        return []
    query  = f"{species} VGC doubles battle move usage role strategy"
    chunks = []
    try:
        for cname in ("vgc_transcripts", "vgc_web"):
            col = _get_collection(cname)
            if col is None or col.count() == 0:
                continue
            results = col.query(query_texts=[query], n_results=RAG_TOP_K,
                                include=["documents", "metadatas"])
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                chunks.append(_format_chunk(doc, meta))
    except Exception:
        pass
    return chunks


# ── Damage matrix ─────────────────────────────────────────────────────────────

def _pokemon_calc_obj(p: dict, data: dict, side: str) -> dict:
    """Build a calc_bridge Pokémon object from state + loaded data."""
    slug     = name_to_slug(p["species"])
    # Use max_offense template for attacker side, max_bulk for defender side
    template = "max_offense" if side == "attacker" else "max_bulk"
    evs      = data.get("ev_templates", {}).get(template, {})
    return {
        "name":       p["species"],
        "species":    p["species"],
        "level":      50,
        "item":       p.get("item"),
        "ability":    p.get("ability"),
        "evs":        evs,
        "boosts":     p.get("boosts") or {},
        "hp_percent": p.get("hp_percent", 1.0),
    }


def build_damage_matrix(state: dict, all_data: dict) -> tuple[list[dict], list[dict]]:
    """
    Pre-compute all relevant damage calcs for this turn.
    Returns (calc_requests, calc_metas) — parallel lists.
    calc_metas contains display info; calc_requests goes to calc_bridge.
    """
    your_active  = state["your_active"]
    opp_active   = state["opponent_active"]
    field        = state.get("field", {})

    base_field = {
        "weather":    field.get("weather"),
        "terrain":    field.get("terrain"),
        "trick_room": field.get("trick_room", False),
    }

    requests: list[dict] = []
    metas: list[dict]    = []

    def add_calc(attacker_p, defender_p, move, friendly_fire, atk_tailwind, def_tailwind):
        atk_slug = name_to_slug(attacker_p["species"])
        def_slug = name_to_slug(defender_p["species"])
        requests.append({
            "attacker": _pokemon_calc_obj(attacker_p, all_data.get(atk_slug, {}), "attacker"),
            "defender": _pokemon_calc_obj(defender_p, all_data.get(def_slug, {}), "defender"),
            "move":     move,
            "field":    {**base_field,
                         "tailwind_attacker": atk_tailwind,
                         "tailwind_defender": def_tailwind},
        })
        metas.append({
            "attacker":      attacker_p["species"],
            "defender":      defender_p["species"],
            "move":          move,
            "friendly_fire": friendly_fire,
            "side":          "your",
        })

    def add_threat(attacker_p, defender_p, move, atk_tailwind, def_tailwind):
        atk_slug = name_to_slug(attacker_p["species"])
        def_slug = name_to_slug(defender_p["species"])
        requests.append({
            "attacker": _pokemon_calc_obj(attacker_p, all_data.get(atk_slug, {}), "attacker"),
            "defender": _pokemon_calc_obj(defender_p, all_data.get(def_slug, {}), "defender"),
            "move":     move,
            "field":    {**base_field,
                         "tailwind_attacker": atk_tailwind,
                         "tailwind_defender": def_tailwind},
        })
        metas.append({
            "attacker":      attacker_p["species"],
            "defender":      defender_p["species"],
            "move":          move,
            "friendly_fire": False,
            "side":          "opponent",
        })

    your_tw = field.get("tailwind_your_side", False)
    opp_tw  = field.get("tailwind_opponent_side", False)

    # ── Your moves vs opponents ───────────────────────────────────────────────
    for i, attacker in enumerate(your_active):
        partner = your_active[1 - i]
        for move in attacker.get("moves", []):
            for defender in opp_active:
                add_calc(attacker, defender, move,
                         friendly_fire=False,
                         atk_tailwind=your_tw, def_tailwind=opp_tw)
            # Friendly fire for all-adjacent spread moves
            if move.lower() in SPREAD_ALL_ADJACENT:
                add_calc(attacker, partner, move,
                         friendly_fire=True,
                         atk_tailwind=your_tw, def_tailwind=your_tw)

    # ── Opponent threats vs your Pokémon ──────────────────────────────────────
    for attacker in opp_active:
        for move in attacker.get("moves", []):
            for defender in your_active:
                add_threat(attacker, defender, move,
                           atk_tailwind=opp_tw, def_tailwind=your_tw)

    return requests, metas


def run_matrix(requests: list[dict]) -> list[dict]:
    if not requests:
        return []
    result = subprocess.run(
        ["node", str(NODE_BRIDGE)],
        input=json.dumps(requests),
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def format_matrix_for_prompt(metas: list[dict], results: list[dict]) -> str:
    """Format damage matrix as a readable table for the Claude prompt."""
    lines = ["## Damage Matrix\n"]
    lines.append("Attacker | Move | Defender | Dmg Range | % HP | OHKO | 2HKO | Note")
    lines.append("---------|------|----------|-----------|------|------|------|-----")

    for meta, result in zip(metas, results):
        if result.get("error"):
            continue
        lo, hi   = result["damage_range"]
        max_hp   = result["defender_max_hp"] or 1
        pct_lo   = round(lo / max_hp * 100)
        pct_hi   = round(hi / max_hp * 100)
        ohko     = "YES" if result["is_ohko"] else "—"
        twohko   = "YES" if result["is_2hko"] else "—"
        note     = "⚠ FRIENDLY FIRE" if meta["friendly_fire"] else ""
        side_tag = "[OPP]" if meta["side"] == "opponent" else ""
        lines.append(
            f"{side_tag}{meta['attacker']} | {meta['move']} | {meta['defender']} | "
            f"{lo}-{hi} | {pct_lo}-{pct_hi}% | {ohko} | {twohko} | {note}"
        )

    return "\n".join(lines)


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_user_message(state: dict, all_data: dict, rag: dict[str, list[str]],
                       matrix_text: str) -> str:
    field  = state.get("field", {})
    lines  = [f"**Turn {state.get('turn', '?')}** — Recommend my best actions.\n"]

    # ── Board state ───────────────────────────────────────────────────────────
    lines.append("<board_state>")

    lines.append("\n### Your Active Pokémon")
    for p in state["your_active"]:
        status  = p.get("status") or "—"
        boosts  = {k: v for k, v in (p.get("boosts") or {}).items() if v != 0}
        lines.append(
            f"- **{p['species']}** | HP: {int(p.get('hp_percent', 1.0)*100)}% | "
            f"Item: {p.get('item') or '?'} | Ability: {p.get('ability') or '?'} | "
            f"Status: {status} | Boosts: {boosts or 'none'}"
        )
        lines.append(f"  Moves: {', '.join(p.get('moves', []))}")

    lines.append("\n### Opponent's Active Pokémon")
    for p in state["opponent_active"]:
        status = p.get("status") or "—"
        boosts = {k: v for k, v in (p.get("boosts") or {}).items() if v != 0}
        moves  = p.get("moves") or []
        lines.append(
            f"- **{p['species']}** | HP: {int(p.get('hp_percent', 1.0)*100)}% | "
            f"Item: {p.get('item') or 'unknown'} | Ability: {p.get('ability') or 'unknown'} | "
            f"Status: {status} | Boosts: {boosts or 'none'}"
        )
        lines.append(f"  Known Moves: {', '.join(moves) if moves else 'none revealed'}")

    lines.append("\n### Your Back Pokémon (available to switch in)")
    for p in state.get("your_back", []):
        lines.append(f"- {p['species']} | HP: {int(p.get('hp_percent', 1.0)*100)}%")

    lines.append("\n### Opponent's Back Pokémon")
    for p in state.get("opponent_back", []):
        lines.append(f"- {p['species']} | HP: {int(p.get('hp_percent', 1.0)*100)}%")

    lines.append("\n### Field Conditions")
    lines.append(f"- Weather: {field.get('weather') or 'None'}")
    lines.append(f"- Terrain: {field.get('terrain') or 'None'}")
    tr     = field.get("trick_room", False)
    tr_t   = field.get("trick_room_turns", 0)
    lines.append(f"- Trick Room: {'Active (' + str(tr_t) + ' turns left)' if tr else 'Inactive'}")
    your_tw = field.get("tailwind_your_side", False)
    opp_tw  = field.get("tailwind_opponent_side", False)
    lines.append(f"- Tailwind (your side): {'Active (' + str(field.get('tailwind_your_turns', 0)) + ' turns)' if your_tw else 'Inactive'}")
    lines.append(f"- Tailwind (opponent): {'Active (' + str(field.get('tailwind_opponent_turns', 0)) + ' turns)' if opp_tw else 'Inactive'}")
    your_screens = field.get("screens_your_side", {})
    opp_screens  = field.get("screens_opponent_side", {})
    if any(your_screens.values()):
        active = [k for k, v in your_screens.items() if v]
        lines.append(f"- Your screens: {', '.join(active)}")
    if any(opp_screens.values()):
        active = [k for k, v in opp_screens.items() if v]
        lines.append(f"- Opponent screens: {', '.join(active)}")

    lines.append("</board_state>\n")

    # ── Damage matrix ─────────────────────────────────────────────────────────
    lines.append(matrix_text)

    # ── RAG context ───────────────────────────────────────────────────────────
    active_with_chunks = {s: c for s, c in rag.items() if c}
    if active_with_chunks:
        lines.append("\n<expert_commentary>")
        lines.append("Relevant player insights for active Pokémon:")
        for species, chunks in active_with_chunks.items():
            lines.append(f"\n### {species}")
            lines.extend(chunks)
        lines.append("</expert_commentary>\n")

    lines.append(
        "Using the board state and damage matrix above, recommend the best action "
        "for each of my Pokémon this turn. Consider KO windows, spread move friendly "
        "fire trade-offs, switch value, and priority order."
    )

    return "\n".join(lines)


# ── XML parsing ───────────────────────────────────────────────────────────────

def extract_tag(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_response(text: str) -> dict:
    return {
        "action_1":          extract_tag(text, "action_1"),
        "action_2":          extract_tag(text, "action_2"),
        "priority_order":    extract_tag(text, "priority_order"),
        "threat_assessment": extract_tag(text, "threat_assessment"),
        "contingency":       extract_tag(text, "contingency"),
        "reasoning":         extract_tag(text, "reasoning"),
    }


# ── Display ───────────────────────────────────────────────────────────────────

def display_result(result: dict, state: dict, metas: list[dict], calc_results: list[dict]) -> None:
    your_active = state["your_active"]

    # ── Green recommendation panel ────────────────────────────────────────────
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan", width=22)
    table.add_column()

    table.add_row(f"Action — {your_active[0]['species']}", result["action_1"])
    table.add_row(f"Action — {your_active[1]['species']}", result["action_2"])
    table.add_row("Priority Order",    result["priority_order"])
    table.add_row("Threat Assessment", result["threat_assessment"])
    table.add_row("Contingency",       result["contingency"])

    console.print(Panel(table, title=f"[bold]Turn {state.get('turn', '?')} Recommendation[/bold]",
                        border_style="green"))

    # ── Reasoning panel ───────────────────────────────────────────────────────
    if result["reasoning"]:
        console.print(Panel(result["reasoning"], title="Reasoning", border_style="dim"))

    # ── Damage matrix table ───────────────────────────────────────────────────
    if calc_results:
        dmg_table = Table(title="Damage Matrix", border_style="dim", show_lines=True)
        dmg_table.add_column("Side",     style="dim",   no_wrap=True)
        dmg_table.add_column("Attacker", style="cyan",  no_wrap=True)
        dmg_table.add_column("Move",                    no_wrap=True)
        dmg_table.add_column("Defender", style="cyan",  no_wrap=True)
        dmg_table.add_column("Dmg",      justify="right")
        dmg_table.add_column("% HP",     justify="right")
        dmg_table.add_column("Result",   justify="center")
        dmg_table.add_column("Note",     style="yellow")

        for meta, res in zip(metas, calc_results):
            if res.get("error"):
                continue
            lo, hi = res["damage_range"]
            max_hp = res["defender_max_hp"] or 1
            pct_lo = round(lo / max_hp * 100)
            pct_hi = round(hi / max_hp * 100)
            result_str = (
                "[bold red]OHKO[/bold red]" if res["is_ohko"]  else
                "[yellow]2HKO[/yellow]"     if res["is_2hko"]  else
                "—"
            )
            side_str = "[dim]opp[/dim]" if meta["side"] == "opponent" else "you"
            note     = "⚠ friendly fire" if meta["friendly_fire"] else ""
            dmg_table.add_row(
                side_str,
                meta["attacker"],
                meta["move"],
                meta["defender"],
                f"{lo}-{hi}",
                f"{pct_lo}-{pct_hi}%",
                result_str,
                note,
            )

        console.print(dmg_table)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 2:
        console.print("[red]Usage:[/red] python scripts/battle_advisor.py <state.json>")
        sys.exit(1)

    state_path = Path(sys.argv[1])
    if not state_path.exists():
        console.print(f"[red]State file not found:[/red] {state_path}")
        sys.exit(1)

    state = json.loads(state_path.read_text())

    # ── Load data ─────────────────────────────────────────────────────────────
    all_active = state["your_active"] + state["opponent_active"]
    console.print(f"[dim]Loading data for {len(all_active)} active Pokémon...[/dim]")
    all_data = {name_to_slug(p["species"]): load_pokemon_data(p["species"]) for p in all_active}

    # ── RAG ───────────────────────────────────────────────────────────────────
    console.print("[dim]Retrieving RAG context...[/dim]")
    rag = {p["species"]: retrieve_rag_context(p["species"]) for p in all_active}
    total_chunks = sum(len(v) for v in rag.values())
    console.print(f"  {total_chunks} chunks retrieved")

    # ── Damage matrix ─────────────────────────────────────────────────────────
    console.print("[dim]Computing damage matrix...[/dim]")
    requests, metas = build_damage_matrix(state, all_data)
    calc_results    = run_matrix(requests)

    friendly_fire_count = sum(1 for m in metas if m["friendly_fire"])
    console.print(f"  {len(requests)} calcs ({friendly_fire_count} friendly fire)")

    matrix_text = format_matrix_for_prompt(metas, calc_results)

    # ── Claude ────────────────────────────────────────────────────────────────
    console.print("[dim]Asking Claude for turn recommendation...[/dim]\n")
    user_msg = build_user_message(state, all_data, rag, matrix_text)

    client   = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    result = parse_response(response.content[0].text)
    display_result(result, state, metas, calc_results)


if __name__ == "__main__":
    main()