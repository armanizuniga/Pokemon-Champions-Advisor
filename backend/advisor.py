"""
Core battle advisor logic — no CLI, no display.
Imported by main.py (FastAPI) and usable by scripts/battle_advisor.py.
"""

import json
import re
import subprocess
from pathlib import Path

import anthropic
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT              = Path(__file__).parents[1]
DATA              = ROOT / "data"
MOVES_PATH        = DATA / "champions/moves.json"
ABILITIES_PATH    = DATA / "champions/abilities.json"
ITEMS_PATH        = DATA / "champions/legal_items.json"
BASE_STATS_PATH   = DATA / "pokeapi/base_stats.json"
EV_TEMPLATES_PATH = DATA / "champions/ev_templates.json"
CHROMADB_PATH     = DATA / "chromadb"
NODE_BRIDGE       = ROOT / "node/calc_bridge.js"
RAG_TOP_K         = 2

SPREAD_ALL_ADJACENT = frozenset({
    "earthquake", "magnitude", "surf", "discharge", "lava plume",
    "bulldoze", "explosion", "self-destruct", "sludge wave",
    "mind blown", "misty explosion", "sparkling aria",
})

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


_data_cache: dict = {}

def _load_json(path: Path) -> dict:
    if str(path) not in _data_cache:
        _data_cache[str(path)] = json.loads(path.read_text())
    return _data_cache[str(path)]


def load_pokemon_data(species: str) -> dict:
    slug = name_to_slug(species)

    moves_data     = _load_json(MOVES_PATH)
    abilities_data = _load_json(ABILITIES_PATH)
    base_stats     = _load_json(BASE_STATS_PATH)
    ev_templates   = _load_json(EV_TEMPLATES_PATH)

    moves     = moves_data.get(slug) or moves_data.get(slug.split("-")[0], [])
    abilities = (
        abilities_data.get(slug)
        or abilities_data.get(slug + "-mega")
        or abilities_data.get(slug.split("-")[0], [])
    )
    stats = base_stats.get(slug) or base_stats.get(slug.split("-")[0], {})
    evs   = ev_templates.get(slug) or ev_templates.get(slug.split("-")[0], {})

    return {
        "species":      species,
        "slug":         slug,
        "moves":        moves,
        "abilities":    abilities,
        "base_stats":   stats,
        "ev_templates": evs,
    }


def load_items() -> list:
    data = _load_json(ITEMS_PATH)
    return data.get("items", data) if isinstance(data, dict) else data


# ── RAG ────────────────────────────────────────────────────────────────────────

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
            results = col.query(
                query_texts=[query],
                n_results=RAG_TOP_K,
                include=["documents", "metadatas"],
            )
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                chunks.append(_format_chunk(doc, meta))
    except Exception:
        pass
    return chunks


# ── Damage matrix ──────────────────────────────────────────────────────────────

def _pokemon_calc_obj(p: dict, data: dict, side: str) -> dict:
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
    your_active = state["your_active"]
    opp_active  = state["opponent_active"]
    field       = state.get("field", {})

    base_field = {
        "weather":    field.get("weather"),
        "terrain":    field.get("terrain"),
        "trick_room": field.get("trick_room", False),
    }

    requests: list[dict] = []
    metas: list[dict]    = []
    your_tw = field.get("tailwind_your_side", False)
    opp_tw  = field.get("tailwind_opponent_side", False)

    def _add(attacker_p, defender_p, move, friendly_fire, atk_tw, def_tw, side):
        atk_slug = name_to_slug(attacker_p["species"])
        def_slug = name_to_slug(defender_p["species"])
        requests.append({
            "attacker": _pokemon_calc_obj(attacker_p, all_data.get(atk_slug, {}), "attacker"),
            "defender": _pokemon_calc_obj(defender_p, all_data.get(def_slug, {}), "defender"),
            "move":     move,
            "field":    {**base_field, "tailwind_attacker": atk_tw, "tailwind_defender": def_tw},
        })
        metas.append({
            "attacker":      attacker_p["species"],
            "defender":      defender_p["species"],
            "move":          move,
            "friendly_fire": friendly_fire,
            "side":          side,
        })

    for i, attacker in enumerate(your_active):
        partner = your_active[1 - i]
        for move in attacker.get("moves", []):
            for defender in opp_active:
                _add(attacker, defender, move, False, your_tw, opp_tw, "your")
            if move.lower() in SPREAD_ALL_ADJACENT:
                _add(attacker, partner, move, True, your_tw, your_tw, "your")

    for attacker in opp_active:
        for move in attacker.get("moves", []):
            for defender in your_active:
                _add(attacker, defender, move, False, opp_tw, your_tw, "opponent")

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
    if result.returncode != 0:
        raise RuntimeError(f"calc_bridge.js error: {result.stderr[:200]}")
    return json.loads(result.stdout)


def format_matrix_for_prompt(metas: list[dict], results: list[dict]) -> str:
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
        note     = "FRIENDLY FIRE" if meta["friendly_fire"] else ""
        side_tag = "[OPP]" if meta["side"] == "opponent" else ""
        lines.append(
            f"{side_tag}{meta['attacker']} | {meta['move']} | {meta['defender']} | "
            f"{lo}-{hi} | {pct_lo}-{pct_hi}% | {ohko} | {twohko} | {note}"
        )

    return "\n".join(lines)


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_user_message(state: dict, all_data: dict, rag: dict[str, list[str]],
                       matrix_text: str) -> str:
    field = state.get("field", {})
    lines = [f"**Turn {state.get('turn', '?')}** — Recommend my best actions.\n"]

    lines.append("<board_state>")

    lines.append("\n### Your Active Pokémon")
    for p in state["your_active"]:
        status = p.get("status") or "—"
        boosts = {k: v for k, v in (p.get("boosts") or {}).items() if v != 0}
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
    tr   = field.get("trick_room", False)
    tr_t = field.get("trick_room_turns", 0)
    lines.append(f"- Trick Room: {'Active (' + str(tr_t) + ' turns left)' if tr else 'Inactive'}")
    your_tw = field.get("tailwind_your_side", False)
    opp_tw  = field.get("tailwind_opponent_side", False)
    lines.append(f"- Tailwind (your side): {'Active (' + str(field.get('tailwind_your_turns', 0)) + ' turns)' if your_tw else 'Inactive'}")
    lines.append(f"- Tailwind (opponent): {'Active (' + str(field.get('tailwind_opponent_turns', 0)) + ' turns)' if opp_tw else 'Inactive'}")
    your_screens = field.get("screens_your_side", {})
    opp_screens  = field.get("screens_opponent_side", {})
    if any(your_screens.values()):
        lines.append(f"- Your screens: {', '.join(k for k, v in your_screens.items() if v)}")
    if any(opp_screens.values()):
        lines.append(f"- Opponent screens: {', '.join(k for k, v in opp_screens.items() if v)}")

    lines.append("</board_state>\n")
    lines.append(matrix_text)

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


# ── XML parsing ────────────────────────────────────────────────────────────────

def _extract_tag(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


# ── Main entry point ───────────────────────────────────────────────────────────

def run_analysis(state: dict) -> dict:
    """
    Full pipeline: load data → RAG → damage matrix → Claude → structured result.
    Returns a dict ready to JSON-serialize for the API response.
    """
    all_active = state["your_active"] + state["opponent_active"]

    all_data = {name_to_slug(p["species"]): load_pokemon_data(p["species"])
                for p in all_active}

    rag = {p["species"]: retrieve_rag_context(p["species"]) for p in all_active}

    requests, metas = build_damage_matrix(state, all_data)
    calc_results    = run_matrix(requests)
    matrix_text     = format_matrix_for_prompt(metas, calc_results)

    user_msg = build_user_message(state, all_data, rag, matrix_text)
    client   = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = response.content[0].text

    recommendation = {
        "action_1":          _extract_tag(raw, "action_1"),
        "action_2":          _extract_tag(raw, "action_2"),
        "priority_order":    _extract_tag(raw, "priority_order"),
        "threat_assessment": _extract_tag(raw, "threat_assessment"),
        "contingency":       _extract_tag(raw, "contingency"),
        "reasoning":         _extract_tag(raw, "reasoning"),
    }

    damage_matrix = []
    for meta, res in zip(metas, calc_results):
        if res.get("error"):
            continue
        lo, hi = res["damage_range"]
        max_hp = res["defender_max_hp"] or 1
        damage_matrix.append({
            "attacker":      meta["attacker"],
            "defender":      meta["defender"],
            "move":          meta["move"],
            "damage_range":  [lo, hi],
            "pct_lo":        round(lo / max_hp * 100),
            "pct_hi":        round(hi / max_hp * 100),
            "is_ohko":       res["is_ohko"],
            "is_2hko":       res["is_2hko"],
            "friendly_fire": meta["friendly_fire"],
            "side":          meta["side"],
        })

    return {
        "recommendation": recommendation,
        "damage_matrix":  damage_matrix,
    }
