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
MOVE_DATA_PATH    = DATA / "champions/move_data.json"
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
3. Assess what the opponent threatens this turn using the damage matrix
4. Provide a contingency if the opponent uses Protect, switches, \
   or makes a surprising play

## Core Battling Principle — Pressure
Every turn, both players move simultaneously. Reason through both sides:
- **Proactive actions**: deal damage, take KOs, set speed control, apply status \
  — these advance your win condition
- **Reactive actions**: Protect, switch, heal — always in response to a threat
- **Pressure** = what threat does each Pokémon apply to the opponent by existing \
  on the field? The opponent will respond to their most urgent threat first.
- Ask every turn: Who moves first? Who threatens KOs? What does the board \
  look like after everyone does their most natural action? \
  What does the opponent fear losing most right now?

## Decision Framework

**1. Check KO windows first (from the damage matrix)**
- A KO denies the opponent an action entirely — this is always the highest-value play
- Check: can you OHKO or 2HKO the opponent's active Pokémon this turn?
- Check: does the opponent OHKO or 2HKO your active Pokémon before you act?
- If you move second and take a KO before you act, factor that into your action

**2. Priority order**
Higher priority resolves first. Within the same bracket, Speed decides.

| Priority | Key Moves |
|---|---|
| +5 | Helping Hand |
| +4 | Protect, Detect, King's Shield, Baneful Bunker, Spiky Shield, Endure |
| +3 | Fake Out, Quick Guard, Wide Guard |
| +2 | Ally Switch, Rage Powder, Follow Me, Feint, Extreme Speed |
| +1 | Quick Attack, Bullet Punch, Aqua Jet, Ice Shard, Mach Punch, \
Shadow Sneak, Jet Punch, Water Shuriken, Sucker Punch, Thunderclap; \
Gale Wings (Talonflame at full HP); Prankster status moves (blocked by Dark-types) |
| 0 | Most moves |
| -7 | Trick Room (always resolves last) |

Priority blockers: Armor Tail (Farigiraf) and Queenly Majesty (Tsareena) \
block all incoming priority moves for themselves and allies. \
Psychic Terrain blocks priority moves against all grounded Pokémon.

**3. Protect value**
Protect is high value when:
- You are threatened with a KO and need to survive to act next turn
- You want to let Trick Room / Tailwind / weather / terrain expire
- You need to scout the opponent's move on a key Pokémon
- Your partner is taking the KO and you want to bring in a better matchup safely

Protect is low value when:
- You have an active KO window you would be giving up
- The opponent can use the free turn to set up or switch to a better matchup
- You used Protect last turn (consecutive Protect is only 1/3 success rate — \
  do not rely on it)

Always ask: what does the opponent do with the free turn if I Protect?

**4. Switching**
Switch when:
- The switch-in resets stat drops (e.g., stacked Intimidate drops — \
  switching out resets them)
- You bring in a dramatically better type matchup
- You need to save a key Pokémon for later in the game
- The incoming Pokémon's ability on entry (Intimidate, etc.) \
  provides immediate value

Do not switch when:
- The switch-in takes heavy damage from the opponent's most natural move
- It does not improve your position next turn
- You are giving up a KO window to do it
- Remember: **1 HP is infinitely more than 0 HP** — a low-HP Pokémon \
  still applies pressure, can Protect, and can take a hit. \
  Do not sacrifice it carelessly.

**5. Spread move and friendly fire logic**
- Earthquake and Rock Slide hit both opponents and your own partner
- Evaluate: does the spread move KO or significantly damage the opponent \
  even if it also chips your partner?
- Sometimes taking chip on your own partner is correct if it secures a KO
- If your partner is on low HP, consider switching it out before using \
  Earthquake to avoid the friendly fire
- Rock Slide has a 30% flinch chance per target — flinch fishing is a \
  legitimate play when the opponent moves first

**6. Prediction vs safe play**
- **Safe play**: an action that produces a good outcome regardless of \
  what the opponent does — always prefer this when available
- **Specific prediction**: calling exactly what the opponent will do — \
  only go for this when:
  - Getting it right wins or significantly swings the game, AND \
    being wrong does not immediately lose it (winning/neutral position)
  - You have no safe play available (losing position)
- Do not over-predict — wrong reads at the wrong time lose games

## Threat Assessment — What Can the Opponent Do?

**Type immunities to check before assessing damage:**
| Defending Type | Immune To |
|---|---|
| Ground | Electric |
| Flying | Ground |
| Ghost | Normal, Fighting |
| Normal | Ghost |
| Steel | Poison |
| Dark | Psychic |
| Fairy | Dragon |

Two-type Pokémon: if both types are weak to the same move → 4x \
("Extremely Effective"). If one resists and one is weak → 1x neutral.

**Key ability interactions that change threat reads:**
- **Intimidate** (Incineroar, Arcanine, Gyarados, Luxray, etc.): \
  Lowers both opponents' Attack on entry — factor this into physical damage math
- **Fake Out immunity**: Inner Focus, Steadfast, Oblivious, Own Tempo, Scrappy, \
  Armor Tail, Queenly Majesty — these Pokémon cannot be flinched by Fake Out
- **Redirection**: Follow Me and Rage Powder pull single-target moves \
  to the user — Stalwart ignores redirection
- **Magic Bounce**: Reflects status moves — Taunt, Icy Wind, and \
  Will-O-Wisp bounce back at the user
- **Unaware** (Clefable, Cofagrigus): Ignores your stat boosts \
  when attacking or being attacked
- **Intimidate immunity**: Clear Body, White Smoke, Hyper Cutter, \
  Mirror Armor; Defiant gets +2 Atk, Competitive gets +2 SpA \
  when stats are lowered by an opponent

## Weather & Terrain — Mid-Battle Awareness
**If weather is active, factor these into damage math:**
- **Harsh Sunlight**: Fire +50%, Water −50%, no Freeze possible
- **Rain**: Water +50%, Fire −50%, Thunder/Hurricane perfect accuracy
- **Sandstorm**: 1/16 HP/turn to non-Rock/Ground/Steel types
- **Snow**: +50% Defense to Ice-types

**If terrain is active (grounded Pokémon only):**
- **Electric Terrain**: Electric +30%, prevents Sleep
- **Psychic Terrain**: Psychic +30%, blocks all priority moves
- **Grassy Terrain**: Grass +30%, heals 1/16 HP/turn, weakens Earthquake
- **Misty Terrain**: Dragon moves halved, prevents all major status conditions \
  — do not recommend status moves if Misty Terrain is active

**Status condition rankings (for recommending status moves):**
Sleep > Burn > Paralysis >>> Poison

**Status immunities:**
- Poison: Poison-type, Steel-type immune
- Burn: Fire-type immune
- Paralysis: Electric-type immune
- Freeze: Ice-type immune
- Powder/Spore: Grass-type, Overcoat immune

## Champions-Specific Mechanics
- **No IVs** — EVs and Natures only; do not reference IVs
- **Paralysis**: 12.5% immobility chance (not 25%) — less punishing than expected
- **Freeze**: Guaranteed thaw by turn 3 — not a permanent threat
- **Unseen Fist**: Only 1/4 damage through Protect — do not factor into damage reads
- **No Flame Orb / Toxic Orb** — Guts, Poison Heal, Marvel Scale \
  strategies are not viable
- **Terrain-setting abilities not in game** — terrain is move-only
- **No Dynamax or Terastallization** — this format does not have either mechanic
- **Salt Cure** (Garganacl): 1/16 HP/turn (1/8 for Water/Steel)
- **Dire Claw** (Sneasler): 30% status chance (not 50%)

## Output Format
Respond using these exact XML tags:

<battle_recommendation>
  <board_state_summary>[Active Pokémon and their approximate HP%. Any status \
conditions on any Pokémon. Field effects currently active and turns remaining \
(Trick Room, Tailwind, weather, terrain, screens).]</board_state_summary>

  <pressure_read>[One sentence: what is the opponent most likely to do this turn, \
and what Pokémon or outcome are they most afraid of?]</pressure_read>

  <action_1>[First Pokémon's action: "Use [Move] on [Target]" \
or "Switch to [Pokémon]"]</action_1>

  <action_2>[Second Pokémon's action: "Use [Move] on [Target]" \
or "Switch to [Pokémon]"]</action_2>

  <threat_assessment>[What the opponent threatens this turn, estimated damage \
from the matrix, and which of your Pokémon is most at risk of going down.]
</threat_assessment>

  <contingency>[If opponent Protects, switches, or surprises: what changes \
and what is the adjusted play — 2 sentences max.]</contingency>

  <reasoning>[Full explanation: KO math from the damage matrix, why this action \
over the alternatives, switch logic if applicable, spread move friendly fire \
rationale if relevant, whether this is a safe play or a prediction and why.]
</reasoning>

  <win_condition>[One sentence: what needs to be true at end of game for the \
user to win from this board state — which Pokémon must be preserved, which \
opponent Pokémon must be eliminated.]</win_condition>

  <speed_tiers>[All active Pokémon ranked fastest to slowest this turn, \
accounting for Trick Room reversal, Tailwind doubling, Choice Scarf, or Speed \
drops. Format: Name (modified Speed) > Name (modified Speed) > Name > Name. \
Then one sentence on what this Speed order means for the actions chosen.]
</speed_tiers>
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


def load_move_data() -> dict:
    return _load_json(MOVE_DATA_PATH)


_ROTOM_FORM_MOVES: dict[str, str] = {
    "rotom-heat":  "Overheat",
    "rotom-wash":  "Hydro Pump",
    "rotom-frost": "Blizzard",
    "rotom-fan":   "Air Slash",
    "rotom-mow":   "Leaf Storm",
}


def load_pokemon_data(species: str) -> dict:
    slug = name_to_slug(species)

    moves_data     = _load_json(MOVES_PATH)
    abilities_data = _load_json(ABILITIES_PATH)
    base_stats     = _load_json(BASE_STATS_PATH)
    ev_templates   = _load_json(EV_TEMPLATES_PATH)

    move_meta  = _load_json(MOVE_DATA_PATH)
    moves      = list(moves_data.get(slug) or moves_data.get(slug.split("-")[0], []))
    # Inject Rotom form signature move if not already present
    if slug in _ROTOM_FORM_MOVES:
        sig = _ROTOM_FORM_MOVES[slug]
        if sig not in moves:
            moves = [sig] + moves
    abilities  = (
        abilities_data.get(slug)
        or abilities_data.get(slug + "-mega")
        or abilities_data.get(slug.split("-")[0], [])
    )
    stats = base_stats.get(slug) or base_stats.get(slug.split("-")[0], {})
    evs   = ev_templates.get(slug) or ev_templates.get(slug.split("-")[0], {})

    move_details = [
        {"name": m, **(move_meta.get(m) or {"type": None, "category": None, "power": 0})}
        for m in moves
    ]

    return {
        "species":      species,
        "slug":         slug,
        "moves":        moves,
        "move_details": move_details,
        "abilities":    abilities,
        "base_stats":   stats,
        "ev_templates": evs,
    }


def load_items() -> list:
    data = _load_json(ITEMS_PATH)
    return data.get("items", data) if isinstance(data, dict) else data


_SPECIAL_NAMES: dict[str, str] = {
    "mr-mime":       "Mr. Mime",
    "mr-rime":       "Mr. Rime",
    "mr-mime-galar": "Mr. Mime (Galar)",
    "ho-oh":         "Ho-Oh",
    "porygon-z":     "Porygon-Z",
    "jangmo-o":      "Jangmo-o",
    "hakamo-o":      "Hakamo-o",
    "kommo-o":       "Kommo-o",
    "chi-yu":        "Chi-Yu",
    "chien-pao":     "Chien-Pao",
    "ting-lu":       "Ting-Lu",
    "wo-chien":      "Wo-Chien",
}


def _slug_to_name(slug: str) -> str:
    if slug in _SPECIAL_NAMES:
        return _SPECIAL_NAMES[slug]
    return " ".join(w.capitalize() for w in slug.split("-"))


def list_pokemon() -> list[dict]:
    data = _load_json(BASE_STATS_PATH)
    return sorted(
        [{"slug": slug, "name": _slug_to_name(slug)} for slug in data if "gmax" not in slug],
        key=lambda x: x["name"],
    )


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

    move_meta = _load_json(MOVE_DATA_PATH)

    def _is_damaging(move_name: str) -> bool:
        return move_meta.get(move_name, {}).get("category") in ("Physical", "Special")

    for i, attacker in enumerate(your_active):
        partner = your_active[1 - i]
        for move in attacker.get("moves", []):
            if not _is_damaging(move):
                continue
            for defender in opp_active:
                _add(attacker, defender, move, False, your_tw, opp_tw, "your")
            if move.lower() in SPREAD_ALL_ADJACENT:
                _add(attacker, partner, move, True, your_tw, your_tw, "your")

    for attacker in opp_active:
        for move in attacker.get("moves", []):
            if not _is_damaging(move):
                continue
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
