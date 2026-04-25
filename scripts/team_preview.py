"""
Phase 2 — Team preview advisor.

Given both players' full teams of 6, recommends which 4 to bring,
which 2 to lead, which 2 to keep in back, and predicts the opponent's
likely gameplan. Uses Claude tool use to run damage calculations via
the Node calc bridge.

Usage:
    python scripts/team_preview.py \
        "Garchomp,Incineroar,Urshifu,Rillaboom,Arcanine,Tornadus" \
        "Zacian,Calyrex,Regieleki,Grimmsnarl,Incineroar,Landorus"
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

console = Console()

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA             = Path(__file__).parents[1] / "data"
MOVES_PATH       = DATA / "champions/moves.json"
ABILITIES_PATH   = DATA / "champions/abilities.json"
ITEMS_PATH       = DATA / "champions/legal_items.json"
BASE_STATS_PATH  = DATA / "pokeapi/base_stats.json"
EV_TEMPLATES_PATH= DATA / "champions/ev_templates.json"
CHROMADB_PATH    = DATA / "chromadb"
NODE_BRIDGE      = Path(__file__).parents[1] / "node/calc_bridge.js"
RAG_TOP_K_USER     = 2
RAG_TOP_K_OPPONENT = 1

# ── Tool definition ───────────────────────────────────────────────────────────

CALC_TOOL = {
    "name": "run_damage_calcs",
    "description": (
        "Run one or more damage calculations using the Smogon damage calculator. "
        "Pass a list of calculations to batch them in a single call. "
        "Each calculation returns damage range, whether it's an OHKO or 2HKO. "
        "Use attacker_spread and defender_spread to bound realistic damage ranges — "
        "e.g. max_offense attacker vs max_bulk defender for worst case, "
        "max_offense vs max_offense for speed tie or offensive mirror checks."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "calculations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "attacker":        {"type": "string", "description": "Species name of attacker"},
                        "attacker_spread": {"type": "string", "enum": ["max_offense", "max_bulk", "trick_room", "max_speed"], "description": "EV preset for attacker"},
                        "defender":        {"type": "string", "description": "Species name of defender"},
                        "defender_spread": {"type": "string", "enum": ["max_offense", "max_bulk", "trick_room", "max_speed"], "description": "EV preset for defender"},
                        "move":            {"type": "string", "description": "Move name"},
                        "field": {
                            "type": "object",
                            "description": "Optional field conditions",
                            "properties": {
                                "weather":           {"type": "string"},
                                "terrain":           {"type": "string"},
                                "trick_room":        {"type": "boolean"},
                                "tailwind_attacker": {"type": "boolean"},
                                "tailwind_defender": {"type": "boolean"},
                            }
                        }
                    },
                    "required": ["attacker", "attacker_spread", "defender", "defender_spread", "move"]
                }
            }
        },
        "required": ["calculations"]
    }
}

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an elite Pokémon VGC team preview coach specializing in Pokémon Champions \
— a doubles format featuring Mega Evolutions unique to this game. You have deep \
knowledge of format mechanics, legal items, priority, weather, terrain, and how \
they differ from previous Pokémon games.

## Your Job at Team Preview
Given both players' full teams of 6, you must:
1. Analyze the opponent's team to identify their likely gameplan, archetype, \
   and lead combinations
2. Select which 4 of the user's 6 Pokémon to bring
3. Decide the lead pair and back pair
4. Provide a contingency if the opponent surprises with an unexpected lead
5. Verify key damage thresholds using the run_damage_calcs tool before finalizing

## Format Rules
- Level 50 doubles (2v2), bring 4 of 6 Pokémon per match
- **No IVs** — stat customization is EVs and Natures only; do not reference IVs
- Mega Evolutions are common — only one Mega per team, making it a major \
  commitment and threat
- Species Clause: only one of each species per team
- No legendaries or mythicals

## Legal Items (do not suggest anything outside this list)
**Hold Items:** Black Belt, Black Glasses, Bright Powder, Charcoal, Choice Scarf, \
Dragon Fang, Fairy Feather, Focus Band, Focus Sash, Hard Stone, King's Rock, \
Leftovers, Light Ball (Pikachu only), Magnet, Mental Herb, Metal Coat, \
Miracle Seed, Mystic Water, Never-Melt Ice, Poison Barb, Quick Claw, Scope Lens, \
Sharp Beak, Shell Bell, Silk Scarf, Silver Powder, Soft Sand, Spell Tag, \
Twisted Spoon, White Herb

**Berries:** Lum Berry, Sitrus Berry, Oran Berry, Chesto Berry, and all \
type-resistance berries (Occa, Passho, Wacan, Rindo, Yache, Chople, Kebia, \
Shuca, Coba, Payapa, Tanga, Charti, Kasib, Haban, Colbur, Babiri, Chilan, Roseli)

**Mega Stones:** Any Mega Stone corresponding to a Pokémon on the team.

Do NOT suggest: Life Orb, Choice Band, Choice Specs, Assault Vest, Rocky Helmet, \
Flame Orb, Toxic Orb, Light Clay, Weakness Policy, Terrain Extender — \
none of these exist in this format.

## Champions-Specific Mechanics (affects matchup reads)
- **Paralysis**: Only 12.5% immobility chance (was 25%) — less punishing than \
  players may expect
- **Freeze**: Guaranteed thaw by turn 3 — no longer a permanent threat
- **No Flame Orb / Toxic Orb**: Guts, Marvel Scale, and Poison Heal are \
  significantly weaker; do not build strategies around them
- **Unseen Fist**: Only deals 1/4 damage through Protect — do not factor this \
  into matchup damage reads
- **Terrain-setting abilities** (Grassy Surge, Psychic Surge, Misty Surge, \
  Electric Surge) are NOT in the game — terrain must be set manually with moves
- **No Dynamax** — there is no Dynamax or Terastallization in this format

## Identifying the Opponent's Archetype
Before selecting your bring, categorize the opponent's team. Common archetypes:

**Speed control based:**
- **Tailwind**: Look for fast, frail setters (Talonflame, Whimsicott) paired \
  with powerful attackers. Beats slow teams, loses to Trick Room.
- **Trick Room**: Look for bulky setters (Cofagrigus, Hatterene, Reuniclus) \
  paired with slow, powerful sweepers. Beats Tailwind, loses to fast offense \
  or Taunt.
- **Icy Wind / Electroweb control**: Speed drops rather than reversal; flexible \
  and harder to counter.

**Combo based (high threat turn 1):**
- **Ability-based**: One Pokémon's ability directly enables a partner \
  (e.g., Drizzle Pelipper + Swift Swim attacker; Drought Torkoal + Chlorophyll)
- **Fake Out + strong attacker**: Disrupts turn 1 and allows a KO setup \
  (e.g., Incineroar + Garchomp)
- **Redirection + setup**: Follow Me or Rage Powder protects a Pokémon \
  while it uses a setup move (e.g., Oranguru + Hatterene)
- **Weather team**: Identify the weather setter (Pelipper = Rain, Torkoal = Sun, \
  Tyranitar/Hippowdon = Sand, Abomasnow/Alolan Ninetales = Snow) and the \
  sweeper that benefits from it

**Win conditions:**
- Identify any Pokémon with "1v4 potential" — one Pokémon that can threaten \
  your entire lineup if unanswered (e.g., Shedinja-immune team, Iron Defense wall)
- Identify their Mega Evolution slot — it is their most invested win condition

## Priority Brackets (critical for turn 1 prediction)
| Priority | Key Moves |
|---|---|
| +5 | Helping Hand |
| +4 | Protect, Detect, King's Shield, Baneful Bunker, Spiky Shield, Endure |
| +3 | Fake Out, Quick Guard, Wide Guard |
| +2 | Ally Switch, Rage Powder, Follow Me, Feint, Extreme Speed |
| +1 | Quick Attack, Bullet Punch, Aqua Jet, Ice Shard, Mach Punch, Shadow Sneak, \
Jet Punch, Water Shuriken, Sucker Punch, Thunderclap; \
Gale Wings (Talonflame, at full HP); Prankster (Whimsicott, Sableye, Klefki — \
status moves only, blocked by Dark-types) |
| -7 | Trick Room (always resolves last in the turn) |

**Priority blocking**: Armor Tail (Farigiraf) and Queenly Majesty (Tsareena) \
block all incoming priority moves for themselves and allies. \
Psychic Terrain blocks priority moves against grounded Pokémon.

## Weather & Terrain (all last 5 turns)
**Weather — identify the setter and sweeper:**
- **Rain** (Drizzle — Pelipper, Politoed): Water +50%, Fire −50%, \
  Thunder/Hurricane perfect accuracy, enables Swift Swim
- **Sun** (Drought — Torkoal): Fire +50%, Water −50%, no Freeze, \
  enables Chlorophyll
- **Sand** (Sand Stream — Tyranitar, Hippowdon): 1/16 HP/turn to \
  non-Rock/Ground/Steel; +50% SpDef to Rock-types
- **Snow** (Snow Warning — Abomasnow, Alolan Ninetales): \
  +50% Defense to Ice-types; enables Aurora Veil

**Terrain — must be set with moves (no auto-terrain abilities in Champions):**
- **Electric Terrain**: Electric +30%, prevents Sleep
- **Psychic Terrain**: Psychic +30%, blocks priority moves
- **Grassy Terrain**: Grass +30%, heals 1/16 HP/turn, weakens Earthquake/Bulldoze
- **Misty Terrain**: Dragon moves halved, **prevents all major status conditions** \
  for all grounded Pokémon — factor this into any status strategy

## Type Immunities (critical for matchup analysis)
| Defending Type | Immune To |
|---|---|
| Ground | Electric |
| Flying | Ground |
| Ghost | Normal, Fighting |
| Normal | Ghost |
| Steel | Poison |
| Dark | Psychic |
| Fairy | Dragon |

Two-type Pokémon: if both types are weak to the same move → 4x damage \
("Extremely Effective"). If one resists and one is weak → neutral (1x).

## Key Abilities for Matchup Reads
- **Intimidate** (Incineroar, Arcanine, Gyarados, etc.): Lowers both opponents' \
  Attack on entry — the most impactful support ability in the format
- **Fake Out immunity**: Inner Focus, Steadfast, Oblivious, Own Tempo, Scrappy, \
  Armor Tail (Farigiraf), Queenly Majesty (Tsareena)
- **Redirection**: Follow Me and Rage Powder pull single-target moves to the user; \
  Stalwart ignores redirection
- **Magic Bounce**: Reflects status moves — Taunt, Icy Wind, Will-O-Wisp all \
  bounce back
- **Prankster**: +1 priority to status moves; Dark-types are immune
- **Unaware** (Clefable, Cofagrigus): Ignores opponent's stat boosts — hard \
  counter to setup sweepers
- **Intimidate immunity**: Inner Focus, Scrappy, Oblivious, Own Tempo, \
  Clear Body, White Smoke, Hyper Cutter, Mirror Armor, Defiant (gets +2 Atk), \
  Competitive (gets +2 SpA)

## Team Preview Decision Framework

### Step 1 — Identify the opponent's gameplan
- What is their primary win condition?
- What are their most threatening lead combinations? \
  (Fake Out + sweeper? Redirection + setup? Weather setter + sweeper?)
- Do they have a Pokémon with 1v4 potential?
- What is their Mega Evolution, and how does it fit their gameplan?
- What is their speed profile — are they fast, Trick Room, or speed-drop based?

### Step 2 — Identify which of your 6 to exclude
Work backwards — eliminate Pokémon that don't contribute:
- **Bad offensive typing**: Your moves don't threaten most of their team
- **Bad defensive typing**: Most of their attacks hit you super effectively \
  and you offer no offensive value in return
- **Wrong speed dynamic**: e.g., a Trick Room-only Pokémon against a \
  Tailwind team
- **Part of a combo you can't complete**: If both halves of a combination \
  can't come together, drop both
- **Island Pokémon**: A Pokémon with no synergy with the rest of your bring — \
  it will sit isolated and do nothing useful

### Step 3 — Select your lead
- Your lead must apply pressure to the opponent's most likely lead
- The lead pair should threaten multiple of the opponent's leads, not just one
- Consider turn 1 priority: who has Fake Out? Who has Protect? \
  Who moves first at base Speed?
- A safe lead has a "safe play" that works against multiple opponent lead options
- Consider what the opponent will expect — leading the obvious combo telegraphs \
  your strategy

### Step 4 — Select your back pair
- Your back two should cover your lead's weaknesses
- At least one of the back Pokémon should be able to answer the opponent's \
  back pair
- Think about what happens if your lead loses a Pokémon early — can the back \
  pair close?

### Step 5 — Prepare a contingency
- If the opponent brings an unexpected lead, what is your pivot?
- Protect + switch is the most common rescue play
- Identify which opponent Pokémon is most dangerous if you misread their lead

## Using the Damage Calculator
Use the run_damage_calcs tool to verify key damage thresholds before finalizing. \
Batch all checks into as few calls as possible. Check:
- Can the opponent's likely lead OHKO or 2HKO your lead?
- Can your lead OHKO or 2HKO the opponent's lead?
- Are there speed tie risks (same base Speed stat)?
- Does your back pair have the damage to clean up their back pair?

## Turn-By-Turn Thinking Framework
When writing the turn-by-turn section, reason through each turn using pressure:
- **Turn 1**: Who applies pressure first? What is the safest proactive play \
  for your lead? What reactive plays does the opponent have? \
  Is there a "safe" move that works regardless of what they do?
- **Turn 2**: Based on the most likely Turn 1 outcome — what does the board \
  look like? Who has the advantage? Are you still applying pressure or \
  reacting to theirs?
- **Turn 3**: What is the win condition at this point? \
  Which Pokémon needs to be alive to close the game?

## Output Format
Respond using these exact XML tags:

<team_preview>
  <bring>[Pokémon 1], [Pokémon 2], [Pokémon 3], [Pokémon 4]</bring>
  <lead>[Pokémon 1], [Pokémon 2]</lead>
  <back>[Pokémon 3], [Pokémon 4]</back>
  <opponent_lead>[predicted opponent lead pair]</opponent_lead>
  <opponent_gameplan>[their archetype, win condition, and key threat]</opponent_gameplan>
  <contingency>[2 sentences max: if opponent surprises with X, pivot to Y and why]</contingency>
  <turn_by_turn>[Turn 1: what each lead does and why. Turn 2: follow-up based on Turn 1 outcome. Turn 3: win condition or pivot.]</turn_by_turn>
  <speed_tiers>[All 12 Pokémon sorted fastest to slowest, accounting for Trick Room or Tailwind if relevant: Name (base Spe) > Name (base Spe) > ...]</speed_tiers>
  <reasoning>[2-3 sentences: why these 4, why this lead, key damage calc findings]</reasoning>
</team_preview>
"""

# ── Data loading ───────────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    return name.lower().strip().replace(" ", "-").replace(".", "").replace("'", "")


def load_pokemon_data(species: str) -> dict:
    slug = name_to_slug(species)

    moves_data     = json.loads(MOVES_PATH.read_text())
    abilities_data = json.loads(ABILITIES_PATH.read_text())
    items_data     = json.loads(ITEMS_PATH.read_text())
    base_stats     = json.loads(BASE_STATS_PATH.read_text())
    ev_templates   = json.loads(EV_TEMPLATES_PATH.read_text())

    moves = moves_data.get(slug) or moves_data.get(slug.split("-")[0], [])
    abilities = (
        abilities_data.get(slug)
        or abilities_data.get(slug + "-mega")
        or abilities_data.get(slug.split("-")[0], [])
    )
    stats = base_stats.get(slug) or base_stats.get(slug.split("-")[0], {})
    evs   = ev_templates.get(slug) or ev_templates.get(slug.split("-")[0], {})
    items = items_data.get("names", [])

    return {
        "species":    species,
        "slug":       slug,
        "moves":      moves,
        "abilities":  abilities,
        "items":      items,
        "base_stats": stats,
        "ev_templates": evs,
    }


# ── RAG ───────────────────────────────────────────────────────────────────────

_chroma_client = None
_chroma_collections: dict = {}

def _get_client():
    global _chroma_client
    if _chroma_client is None:
        embed_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        _chroma_client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
        _chroma_client._embed_fn = embed_fn
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


def retrieve_rag_context(species: str, top_k: int = RAG_TOP_K_USER) -> list[str]:
    if not CHROMADB_PATH.exists():
        return []
    query  = f"{species} VGC moveset item EV spread role doubles strategy"
    chunks = []
    try:
        for cname in ("vgc_transcripts", "vgc_web"):
            col = _get_collection(cname)
            if col is None or col.count() == 0:
                continue
            results = col.query(query_texts=[query], n_results=top_k, include=["documents", "metadatas"])
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                chunks.append(_format_chunk(doc, meta))
    except Exception:
        pass
    return chunks


def retrieve_team_preview_context() -> list[str]:
    if not CHROMADB_PATH.exists():
        return []
    chunks = []
    try:
        for query in [
            "team preview lead selection doubles VGC strategy",
            "which four to bring team building VGC doubles gameplan",
        ]:
            for cname in ("vgc_transcripts", "vgc_web"):
                col = _get_collection(cname)
                if col is None or col.count() == 0:
                    continue
                results = col.query(query_texts=[query], n_results=2, include=["documents", "metadatas"])
                for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                    chunks.append(_format_chunk(doc, meta))
    except Exception:
        pass
    return chunks


# ── Damage calc tool ──────────────────────────────────────────────────────────

def run_damage_calcs(calculations: list, all_pokemon: dict) -> list:
    requests = []
    for calc in calculations:
        attacker_data = all_pokemon.get(name_to_slug(calc["attacker"]), {})
        defender_data = all_pokemon.get(name_to_slug(calc["defender"]), {})

        attacker_evs = attacker_data.get("ev_templates", {}).get(calc["attacker_spread"], {})
        defender_evs = defender_data.get("ev_templates", {}).get(calc["defender_spread"], {})

        requests.append({
            "attacker": {
                "name":    calc["attacker"],
                "species": calc["attacker"],
                "level":   50,
                "evs":     attacker_evs,
                "nature":  "Hardy",
            },
            "defender": {
                "name":    calc["defender"],
                "species": calc["defender"],
                "level":   50,
                "evs":     defender_evs,
                "nature":  "Hardy",
            },
            "move":  calc["move"],
            "field": calc.get("field", {}),
        })

    result = subprocess.run(
        ["node", str(NODE_BRIDGE)],
        input=json.dumps(requests),
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_user_message(
    user_team: list[dict],
    opponent_team: list[dict],
    user_rag: dict[str, list[str]],
    opponent_rag: dict[str, list[str]],
    team_rag: list[str],
) -> str:
    lines = ["Analyze this team preview and recommend my best team selection and lead.\n"]

    # User team
    lines.append("<user_team>")
    for p in user_team:
        lines.append(f"\n## {p['species']}")
        lines.append(f"Base Stats: {p['base_stats']}")
        lines.append(f"Abilities: {', '.join(p['abilities'])}")
        lines.append(f"Moves: {', '.join(p['moves'])}")
    lines.append("</user_team>\n")

    # Opponent team
    lines.append("<opponent_team>")
    for p in opponent_team:
        lines.append(f"\n## {p['species']}")
        lines.append(f"Base Stats: {p['base_stats']}")
        lines.append(f"Abilities: {', '.join(p['abilities'])}")
        lines.append(f"Moves: {', '.join(p['moves'])}")
    lines.append("</opponent_team>\n")

    # Legal items (shared)
    lines.append("<legal_items>")
    lines.extend(f"- {i}" for i in user_team[0]["items"])
    lines.append("</legal_items>\n")

    # User RAG
    if any(user_rag.values()):
        lines.append("<user_team_commentary>")
        lines.append("Expert commentary on your Pokemon:")
        for species, chunks in user_rag.items():
            if chunks:
                lines.append(f"\n### {species}")
                lines.extend(chunks)
        lines.append("</user_team_commentary>\n")

    # Opponent RAG
    if any(opponent_rag.values()):
        lines.append("<opponent_team_commentary>")
        lines.append("Expert commentary on the opponent's Pokemon — use this to model their likely sets and gameplan:")
        for species, chunks in opponent_rag.items():
            if chunks:
                lines.append(f"\n### {species}")
                lines.extend(chunks)
        lines.append("</opponent_team_commentary>\n")

    # Team preview RAG
    if team_rag:
        lines.append("<team_preview_strategy>")
        lines.append("General team preview and lead selection insights from top players:")
        lines.extend(team_rag)
        lines.append("</team_preview_strategy>\n")

    lines.append(
        "Use the damage calculator to check key matchups, then provide your "
        "full team preview recommendation in the XML format specified."
    )

    return "\n".join(lines)


# ── XML parsing ───────────────────────────────────────────────────────────────

def extract_tag(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_response(text: str) -> dict:
    return {
        "bring":             extract_tag(text, "bring"),
        "lead":              extract_tag(text, "lead"),
        "back":              extract_tag(text, "back"),
        "opponent_lead":     extract_tag(text, "opponent_lead"),
        "opponent_gameplan": extract_tag(text, "opponent_gameplan"),
        "contingency":       extract_tag(text, "contingency"),
        "turn_by_turn":      extract_tag(text, "turn_by_turn"),
        "speed_tiers":       extract_tag(text, "speed_tiers"),
        "reasoning":         extract_tag(text, "reasoning"),
    }


# ── Display ───────────────────────────────────────────────────────────────────

def _lead_calc_rows(all_calcs: list, lead_names: set, opponent_lead_names: set) -> str:
    """Format damage calcs involving the lead Pokemon as compact text."""
    rows = []
    for calc_input, calc_result in all_calcs:
        a = calc_result.get("attacker", "")
        d = calc_result.get("defender", "")
        if not ({a.lower(), d.lower()} & (lead_names | opponent_lead_names)):
            continue
        if calc_result.get("error"):
            continue
        lo, hi  = calc_result["damage_range"]
        max_hp  = calc_result["defender_max_hp"] or 1
        pct_lo  = round(lo / max_hp * 100)
        pct_hi  = round(hi / max_hp * 100)
        ko_tag  = " [OHKO]" if calc_result["is_ohko"] else " [2HKO]" if calc_result["is_2hko"] else ""
        rows.append(f"{a} → {calc_result['move']} → {d}: {pct_lo}-{pct_hi}%{ko_tag}")
    return "\n".join(rows) if rows else "—"


def display_result(result: dict, all_calcs: list) -> None:
    # Parse lead names for filtering
    lead_names          = {n.strip().lower() for n in result["lead"].split(",")}
    opponent_lead_names = {n.strip().lower() for n in result["opponent_lead"].split(",")}

    # ── Green summary panel ───────────────────────────────────────────────────
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan", width=20)
    table.add_column()

    table.add_row("Bring",             result["bring"])
    table.add_row("Lead",              result["lead"])
    table.add_row("Back",              result["back"])
    table.add_row("Opponent Lead",     result["opponent_lead"])
    table.add_row("Opponent Gameplan", result["opponent_gameplan"])
    table.add_row("Contingency",       result["contingency"])

    if result["turn_by_turn"]:
        table.add_row("Turn by Turn",  result["turn_by_turn"])

    if result["speed_tiers"]:
        table.add_row("Speed Tiers",   result["speed_tiers"])

    lead_calcs_text = _lead_calc_rows(all_calcs, lead_names, opponent_lead_names)
    table.add_row("Lead Calcs",        lead_calcs_text)

    console.print(Panel(table, title="[bold]Team Preview Recommendation[/bold]", border_style="green"))

    # ── Reasoning panel ───────────────────────────────────────────────────────
    if result["reasoning"]:
        console.print(Panel(result["reasoning"], title="Reasoning", border_style="dim"))

    # ── Full damage calc table ────────────────────────────────────────────────
    if all_calcs:
        calc_table = Table(title="Damage Calculations", border_style="dim", show_lines=True)
        calc_table.add_column("Attacker",  style="cyan",  no_wrap=True)
        calc_table.add_column("Spread",    style="dim",   no_wrap=True)
        calc_table.add_column("Move",      no_wrap=True)
        calc_table.add_column("Defender",  style="cyan",  no_wrap=True)
        calc_table.add_column("Spread",    style="dim",   no_wrap=True)
        calc_table.add_column("Dmg Range", justify="right")
        calc_table.add_column("% HP",      justify="right")
        calc_table.add_column("Result",    justify="center")

        for calc_input, calc_result in all_calcs:
            if calc_result.get("error"):
                continue
            lo, hi  = calc_result["damage_range"]
            max_hp  = calc_result["defender_max_hp"] or 1
            pct_lo  = round(lo / max_hp * 100)
            pct_hi  = round(hi / max_hp * 100)
            result_str = (
                "[bold red]OHKO[/bold red]"  if calc_result["is_ohko"]  else
                "[yellow]2HKO[/yellow]"      if calc_result["is_2hko"]  else
                "—"
            )
            calc_table.add_row(
                calc_result["attacker"],
                calc_input.get("attacker_spread", ""),
                calc_result["move"],
                calc_result["defender"],
                calc_input.get("defender_spread", ""),
                f"{lo}-{hi}",
                f"{pct_lo}-{pct_hi}%",
                result_str,
            )

        console.print(calc_table)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 3:
        console.print('[red]Usage:[/red] python scripts/team_preview.py "Mon1,Mon2,..." "Opp1,Opp2,..."')
        sys.exit(1)

    user_names     = [s.strip() for s in sys.argv[1].split(",")]
    opponent_names = [s.strip() for s in sys.argv[2].split(",")]

    if len(user_names) != 6 or len(opponent_names) != 6:
        console.print("[red]Each team must have exactly 6 Pokemon.[/red]")
        sys.exit(1)

    console.print("[dim]Loading data for all 12 Pokemon...[/dim]")
    user_team     = [load_pokemon_data(n) for n in user_names]
    opponent_team = [load_pokemon_data(n) for n in opponent_names]

    # Build lookup dict keyed by slug for damage calc
    all_pokemon = {p["slug"]: p for p in user_team + opponent_team}

    console.print("[dim]Retrieving RAG context...[/dim]")
    user_rag     = {p["species"]: retrieve_rag_context(p["species"], RAG_TOP_K_USER) for p in user_team}
    opponent_rag = {p["species"]: retrieve_rag_context(p["species"], RAG_TOP_K_OPPONENT) for p in opponent_team}
    team_rag     = retrieve_team_preview_context()

    user_chunks     = sum(len(v) for v in user_rag.values())
    opponent_chunks = sum(len(v) for v in opponent_rag.values())
    console.print(f"  {user_chunks} user chunks, {opponent_chunks} opponent chunks, {len(team_rag)} team-level chunks")

    console.print("[dim]Running team preview analysis...[/dim]\n")

    client   = anthropic.Anthropic()
    messages = [{
        "role":    "user",
        "content": build_user_message(user_team, opponent_team, user_rag, opponent_rag, team_rag),
    }]

    # Tool use loop
    tool_call_count = 0
    all_calcs       = []  # list of (calc_input, calc_result) for display

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[CALC_TOOL],
            messages=messages,
        )

        # Collect any text content for final parsing
        text_content = ""
        tool_uses    = []

        for block in response.content:
            if block.type == "text":
                text_content = block.text
            elif block.type == "tool_use":
                tool_uses.append(block)

        # If no tool calls, we're done
        if not tool_uses:
            break

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # Process all tool calls and build tool_result blocks
        tool_results = []
        for tool_use in tool_uses:
            tool_call_count += 1
            calcs = tool_use.input["calculations"]
            console.print(f"  [dim]Damage calc batch #{tool_call_count}: {len(calcs)} calculation(s)[/dim]")

            results = run_damage_calcs(calcs, all_pokemon)
            all_calcs.extend(zip(calcs, results))

            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": tool_use.id,
                "content":     json.dumps(results),
            })

        messages.append({"role": "user", "content": tool_results})

    result = parse_response(text_content)
    display_result(result, all_calcs)


if __name__ == "__main__":
    main()