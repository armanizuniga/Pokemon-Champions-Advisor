"""
Phase 1 — Single Pokemon moveset suggester.

Loads Champions-legal moves, abilities, and items for a species,
then asks Claude to recommend a competitive VGC moveset.

Usage:
    python scripts/moveset_suggest.py Garchomp
    python scripts/moveset_suggest.py "Mr. Rime"
"""

import json
import re
import sys
from pathlib import Path

import anthropic
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── Data paths ────────────────────────────────────────────────────────────────
DATA           = Path(__file__).parents[1] / "data"
MOVES_PATH     = DATA / "champions/moves.json"
ABILITIES_PATH = DATA / "champions/abilities.json"
ITEMS_PATH     = DATA / "champions/legal_items.json"
CHROMADB_PATH  = DATA / "chromadb"
RAG_TOP_K      = 4

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an elite Pokémon VGC coach specializing in Pokémon Champions — \
a doubles format featuring Mega Evolutions unique to this game. \
You have deep knowledge of the format's rules, mechanics, legal items, \
abilities, and how they differ from previous Pokémon games.

## Format Rules
- Level 50 doubles (2v2), bring 4 of 6 Pokémon to each match
- Mega Evolutions are available and common — factor Mega Stone items and \
  post-Mega ability changes into every role assessment
- No IVs exist in this format — stat customization comes from EVs and Natures only
- Species Clause: only one of each species per team
- No legendaries or mythicals are permitted
- Always speak to both the base form and Mega form when relevant

## Legal Items Only
Only these items are available. Do NOT suggest Life Orb, Choice Band, \
Choice Specs, Assault Vest, Flame Orb, Toxic Orb, Light Clay, \
Weakness Policy, or Terrain Extender — they do not exist in this format.

**Hold Items:** Black Belt, Black Glasses, Bright Powder, Charcoal, \
Choice Scarf, Dragon Fang, Fairy Feather, Focus Band, Focus Sash, \
Hard Stone, King's Rock, Leftovers, Light Ball (Pikachu only), Magnet, \
Mental Herb, Metal Coat, Miracle Seed, Mystic Water, Never-Melt Ice, \
Poison Barb, Quick Claw, Scope Lens, Sharp Beak, Shell Bell, Silk Scarf, \
Silver Powder, Soft Sand, Spell Tag, Twisted Spoon, White Herb

**Berries:** Lum Berry, Sitrus Berry, Oran Berry, Chesto Berry, \
Aspear Berry, Cheri Berry, Pecha Berry, Rawst Berry, \
and all resistance berries (Occa, Passho, Wacan, Rindo, Yache, Chople, \
Kebia, Shuca, Coba, Payapa, Tanga, Charti, Kasib, Haban, Colbur, \
Babiri, Chilan, Roseli)

**Mega Stones:** Any Mega Stone corresponding to the Pokémon being built.

## Champions-Specific Mechanics (differs from previous games)
- **No IVs** — do not reference IV optimization
- **Paralysis**: Only 12.5% chance of full immobility (was 25%)
- **Freeze**: Guaranteed to thaw by turn 3 (was potentially permanent)
- **Rest sleep**: Lasts 3 turns (was 2)
- **Unseen Fist**: Only deals 1/4 damage through Protect (was full damage)
- **Salt Cure**: 1/16 HP/turn (1/8 for Water/Steel) — down from 1/8 (1/4)
- **Dire Claw**: Status chance reduced to 30% (was 50%)
- **Timer tie**: Results in a draw based on Pokémon count, not HP%
- **No Flame Orb / Toxic Orb**: Guts, Marvel Scale, and Poison Heal \
  are significantly weaker as a result
- Terrain-setting abilities (Grassy Surge, Psychic Surge, etc.) \
  are NOT in the game — terrain must be set manually with moves

## Priority Brackets (critical for doubles)
Higher priority resolves first. Within the same bracket, Speed decides order.

| Priority | Key Moves |
|---|---|
| +5 | Helping Hand |
| +4 | Protect, Detect, King's Shield, Baneful Bunker, Spiky Shield, Endure |
| +3 | Fake Out, Quick Guard, Wide Guard |
| +2 | Ally Switch, Rage Powder, Follow Me, Feint, Extreme Speed |
| +1 | Quick Attack, Bullet Punch, Aqua Jet, Ice Shard, Mach Punch, \
Shadow Sneak, Jet Punch, Water Shuriken, Accelerock, Sucker Punch, \
Thunderclap; Gale Wings (at full HP); Prankster (status moves, \
blocked by Dark-types) |
| -7 | Trick Room (always goes last — use this when setting TR) |

Priority-blocking abilities: **Armor Tail** (Farigiraf) and \
**Queenly Majesty** (Tsareena) block all incoming priority moves. \
**Psychic Terrain** blocks priority moves against grounded Pokémon.

## Weather & Terrain (all last 5 turns)
**Weather (set by ability or move):**
- Harsh Sunlight: Fire +50%, Water −50%, no Freeze, enables Chlorophyll
- Rain: Water +50%, Fire −50%, Thunder/Hurricane perfect accuracy, \
  enables Swift Swim
- Sandstorm: 1/16 HP/turn to non-Rock/Ground/Steel; +50% SpDef to Rock
- Snow: +50% Defense to Ice-types; enables Aurora Veil

**Terrain (move-only, affects grounded Pokémon only):**
- Electric Terrain: Electric +30%, prevents Sleep
- Psychic Terrain: Psychic +30%, blocks priority moves
- Grassy Terrain: Grass +30%, heals 1/16 HP/turn, weakens Earthquake
- Misty Terrain: Dragon moves halved, prevents all major status conditions

## Status Conditions in Doubles
Use these rankings when recommending status-inflicting moves:
Sleep > Burn > Paralysis >>> Poison (don't bother with Toxic in doubles)

Status type immunities:
- Poison/Badly Poisoned: immune — Poison-type, Steel-type
- Burn: immune — Fire-type
- Paralysis: immune — Electric-type
- Freeze: immune — Ice-type
- Powder/Spore moves: immune — Grass-type, Overcoat ability

**Misty Terrain** completely prevents status for all grounded Pokémon — \
factor this into any status-based strategy.

## Key Competitive Abilities to Know
- **Intimidate**: Lowers both opponents' Attack on entry — extremely strong
- **Prankster**: +1 priority to status moves; blocked by Dark-types
- **Fake Out immunity**: Inner Focus, Steadfast, Oblivious, Own Tempo, \
  Scrappy, Armor Tail (blocks all priority)
- **Redirection**: Follow Me and Rage Powder redirect single-target moves \
  to the user — Stalwart ability ignores this
- **Magic Bounce**: Reflects status moves — be careful recommending Taunt, \
  Will-O-Wisp, Icy Wind against potential Magic Bounce users
- **Unaware**: Ignores stat boosts when attacking or being attacked — \
  counters setup sweepers
- **Unseen Fist**: Only 1/4 damage through Protect — do not build around this

## Moveset Philosophy (from top player insights)
- **Speed tiers are critical.** Max Speed is often correct — dropping Speed \
  investment means more Pokémon can outpace you. Only drop Speed when you \
  have a specific bulk benchmark to hit first.
- **EV spreads should target benchmarks**, not default to 252/252/4. Ask: \
  what does this Pokémon need to survive, and what does it need to outspeed?
- **Speed control is a pillar of the format.** Icy Wind, Tailwind, and \
  Trick Room shape how an entire moveset is built — include speed control \
  where it fits the role. Aim for at least two forms of speed control \
  across the team.
- **Item choice defines role.** Choice Scarf for speed, Focus Sash for \
  fragile setters, Mega Stones to enable Mega Evolution, Berries for \
  situational bulk, type-boosting items for wallbreakers.
- **Focus Sash** is best for fragile leads that must survive one hit to set \
  up (Trick Room or Tailwind setters). Avoid it on bulky Pokémon, \
  Mega Evolution users (they need their Mega Stone), or Pokémon that \
  typically come in off the bench.
- **Protect is almost always worth a slot.** In doubles, Protect scouts, \
  stalls field effects, shields from Fake Out, and enables positioning. \
  Every moveset should have a reason not to run Protect — not the other \
  way around.
- **Every move slot must earn its place.** Four moves, four jobs: \
  coverage, utility, speed control, and/or protection.
- **Fake Out** is near-mandatory on support Pokémon. It flinches the target \
  on the user's first turn on the field (+3 priority) and combos with a \
  partner's attack to take a KO safely.
- **Trick Room setters** should minimize Speed EVs and run very bulky \
  spreads — they need to survive to set TR.
- **Mega Evolution users** must always hold their corresponding Mega Stone. \
  Consider both the base ability/stats and post-Mega ability/stats when \
  building the role.
- **Mirror matchups matter.** A few Speed EVs to edge out an opposing \
  same-species Pokémon can decide games.
- **Consider synergy, not just the individual set.** Does this Pokémon \
  have redirection support? Does it benefit from Tailwind? Can it be \
  safely swapped in with a partner using Fake Out?

## Team Composition Reminders
When evaluating or suggesting sets, always consider:
- Does the team have speed control? (Tailwind, Trick Room, Icy Wind)
- Does the team have redirection? (Follow Me, Rage Powder)
- Does the team have Fake Out support?
- Is Intimidate on the team? (near-mandatory in most builds)
- Does the team have offensive and defensive synergy across typings?
- Are there "Island Pokémon" — team members with no meaningful synergy?

## Few-Shot Examples

**Incineroar** (bulky support):
<moveset>
  <ability>Intimidate</ability>
  <item>Sitrus Berry</item>
  <nature>Careful</nature>
  <evs><hp>252</hp><atk>4</atk><def>0</def><spa>0</spa><spd>252</spd><spe>0</spe></evs>
  <moves>
    <move>Fake Out</move>
    <move>Parting Shot</move>
    <move>Flare Blitz</move>
    <move>Protect</move>
  </moves>
  <reasoning>Incineroar's role is disruption — Fake Out flinches on turn 1, \
Parting Shot pivots out while dropping both opponents' offensive stats, \
and Intimidate on every switch-in compounds that debuff. Max HP / Max SpDef \
with Careful lets it absorb special hits reliably. Sitrus Berry extends \
survivability so it can Fake Out and Parting Shot multiple times per game. \
Protect is mandatory in doubles. Speed investment is irrelevant — this \
Pokémon wants to be slower so Parting Shot undercuts opponents in \
Trick Room matchups.</reasoning>
</moveset>

**Garchomp** (fast physical attacker / speed control):
<moveset>
  <ability>Rough Skin</ability>
  <item>Garchompite</item>
  <nature>Jolly</nature>
  <evs><hp>4</hp><atk>252</atk><def>0</def><spa>0</spa><spd>0</spd><spe>252</spe></evs>
  <moves>
    <move>Earthquake</move>
    <move>Rock Slide</move>
    <move>Icy Wind</move>
    <move>Protect</move>
  </moves>
  <reasoning>Max Speed Jolly is required — dropping Speed allows opposing \
Garchomps and Adamant spreads to outpace you, which loses games. \
Garchompite enables Mega Evolution for significantly increased Attack and \
Speed. Earthquake and Rock Slide are the core spread damage moves in \
doubles, hitting both targets. Icy Wind provides speed control that lets \
partners outpace after activation. Protect is mandatory in doubles — \
scouting and surviving one turn of pressure is often game-deciding.</reasoning>
</moveset>

## Output Format
Always respond using these exact XML tags:

<moveset>
  <ability>[ability name]</ability>
  <item>[item name]</item>
  <nature>[nature name]</nature>
  <evs>
    <hp>[0-252]</hp>
    <atk>[0-252]</atk>
    <def>[0-252]</def>
    <spa>[0-252]</spa>
    <spd>[0-252]</spd>
    <spe>[0-252]</spe>
  </evs>
  <moves>
    <move>[move 1]</move>
    <move>[move 2]</move>
    <move>[move 3]</move>
    <move>[move 4]</move>
  </moves>
  <reasoning>[3-5 sentences explaining the role, key EV benchmarks hit, \
item choice rationale, and how this set fits into a doubles team]</reasoning>
</moveset>
"""


def build_user_message(species: str, moves: list[str], abilities: list[str], items: list[str], rag_chunks: list[str] | None = None) -> str:
    lines = [f"Build a competitive VGC doubles moveset for {species}.\n"]

    if rag_chunks:
        lines.append("<expert_commentary>")
        lines.append(
            "The following is commentary from top VGC players about this Pokemon. "
            "Use these insights to inform your EV benchmarks, item selection, move choices, and role framing. "
            "Prioritize any specific numbers or strategies mentioned (e.g. speed tiers, key damage thresholds)."
        )
        for chunk in rag_chunks:
            lines.append(f"\n{chunk}")
        lines.append("</expert_commentary>\n")

    lines.append(f"<available_abilities>")
    lines.extend(f"- {a}" for a in abilities)
    lines.append("</available_abilities>\n")

    lines.append("<available_moves>")
    lines.extend(f"- {m}" for m in moves)
    lines.append("</available_moves>\n")

    lines.append("<legal_items>")
    lines.extend(f"- {i}" for i in items)
    lines.append("</legal_items>\n")

    lines.append(f"Recommend the strongest competitive set for {species} in Pokemon Champions doubles. "
                 "Choose only from the moves and abilities listed above, and only from the legal items list.")

    return "\n".join(lines)


# ── Data loading ──────────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace(".", "").replace("'", "")


def load_data(species: str) -> tuple[list[str], list[str], list[str]]:
    slug = name_to_slug(species)

    moves_data = json.loads(MOVES_PATH.read_text())
    abilities_data = json.loads(ABILITIES_PATH.read_text())
    items_data = json.loads(ITEMS_PATH.read_text())

    moves = moves_data.get(slug)
    if not moves:
        # Try stripping regional/form suffixes to find base species
        base = slug.split("-")[0]
        moves = moves_data.get(base, [])

    abilities = abilities_data.get(slug) or abilities_data.get(slug + "-mega") or []
    if not abilities:
        base = slug.split("-")[0]
        abilities = abilities_data.get(base, [])

    items = items_data.get("names", [])

    return moves, abilities, items


# ── RAG retrieval ─────────────────────────────────────────────────────────────

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


def retrieve_rag_context(species: str) -> list[str]:
    """Query ChromaDB for top player commentary relevant to this species."""
    if not CHROMADB_PATH.exists():
        return []
    query  = f"{species} VGC moveset item EV spread role doubles strategy"
    chunks = []
    try:
        for cname in ("vgc_transcripts", "vgc_web"):
            col = _get_collection(cname)
            if col is None or col.count() == 0:
                continue
            results = col.query(query_texts=[query], n_results=RAG_TOP_K, include=["documents", "metadatas"])
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                chunks.append(_format_chunk(doc, meta))
    except Exception:
        pass
    return chunks


# ── XML parsing ───────────────────────────────────────────────────────────────

def extract_tag(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1).strip() if match else ""


def parse_response(text: str) -> dict:
    evs = {}
    for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
        val = extract_tag(text, stat)
        evs[stat] = int(val) if val.isdigit() else 0

    moves = re.findall(r"<move>(.*?)</move>", text, re.DOTALL)

    return {
        "ability":   extract_tag(text, "ability"),
        "item":      extract_tag(text, "item"),
        "nature":    extract_tag(text, "nature"),
        "evs":       evs,
        "moves":     [m.strip() for m in moves],
        "reasoning": extract_tag(text, "reasoning"),
    }


# ── Display ───────────────────────────────────────────────────────────────────

def display_moveset(species: str, result: dict) -> None:
    ev = result["evs"]
    ev_str = " / ".join(
        f"{v} {k.upper()}" for k, v in ev.items() if v > 0
    )

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="bold cyan", width=12)
    table.add_column()

    table.add_row("Ability",  result["ability"])
    table.add_row("Item",     result["item"])
    table.add_row("Nature",   result["nature"])
    table.add_row("EVs",      ev_str or "none")
    table.add_row("Moves",    "\n".join(f"• {m}" for m in result["moves"]))

    console.print(Panel(table, title=f"[bold]{species}[/bold]", border_style="green"))
    console.print(Panel(result["reasoning"], title="Reasoning", border_style="dim"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        console.print("[red]Usage:[/red] python scripts/moveset_suggest.py <Pokemon name>")
        sys.exit(1)

    species = " ".join(sys.argv[1:])
    console.print(f"[dim]Loading data for {species}...[/dim]")

    moves, abilities, items = load_data(species)

    if not moves:
        console.print(f"[red]No moves found for '{species}'. Check the name matches legal_pokemon list.[/red]")
        sys.exit(1)

    console.print(f"  {len(moves)} moves, {len(abilities)} abilities, {len(items)} items loaded")

    console.print("[dim]Retrieving context from ChromaDB...[/dim]")
    rag_chunks = retrieve_rag_context(species)
    console.print(f"  {len(rag_chunks)} relevant chunks retrieved")

    console.print("[dim]Asking Claude for a moveset recommendation...[/dim]\n")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_user_message(species, moves, abilities, items, rag_chunks)
        }],
    )

    raw = response.content[0].text
    result = parse_response(raw)
    display_moveset(species, result)


if __name__ == "__main__":
    main()