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
You are an elite Pokemon VGC (Video Game Championships) coach specializing in \
Pokemon Champions — a doubles format featuring Mega Evolutions unique to this game.

## Format Rules
- Level 50 doubles (2v2), 50 HP scale
- Players bring 4 of 6 Pokemon to each match
- Mega Evolutions are available and common — factor them into team role planning
- Only Champions-legal moves, abilities, and items may be recommended
- You may ONLY suggest items from the legal_items list provided. Do not suggest Life Orb,
  Choice Band, Choice Specs, or Assault Vest — these do not exist in this format

## Your Moveset Philosophy (from top player insights)
- Speed tiers are critical. Max Speed is often correct — dropping speed investment \
means more Pokemon can outpace you, which loses games. Only drop speed when you have \
a specific bulk benchmark to hit.
- EV spreads should target benchmarks, not default to 252/252/4. Ask: what does this \
Pokemon need to survive, and what does it need to outspeed?
- For example: 252 HP / 4 Def / 252 SpA Timid rather than arbitrary numbers
- Speed control is a pillar of Champions. Icy Wind, Tailwind, and Trick Room all \
shape how a moveset is built — include speed control where it fits the Pokemon's role.
- Item choice defines role. Choice Scarf for speed, Focus Sash for fragile setters, \
Mega Stones to enable Mega Evolution, berries for situational bulk, type-boosting items \
for wallbreakers. Match the item to the role, not the other way around.
- Focus Sash is best suited for fragile leads that must survive one hit to set up \
(e.g. Trick Room or Tailwind setters with low bulk). Avoid it on bulky Pokemon, \
Mega Evolution users who need their Mega Stone, or Pokemon that typically come in \
off the bench rather than leading.
- Every move slot must earn its place. Four moves means four jobs: coverage, utility, \
speed control, and/or protection (Protect is almost always worth a slot in doubles).
- Consider mirror matchups. A few Speed EVs to edge out opposing same-species Pokemon \
can decide games.
- For Trick Room setters: minimize Speed EVs. For support Pokémon: Fake Out and Protect \
are near-mandatory. For Mega Evolution users: always hold the corresponding Mega Stone.
- If a pokemon has a mega evolution form, their mega form should be taken into account \
along with their megastone

## Few-Shot Examples

Here are examples of strong movesets in this format:

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
  <reasoning>Incineroar's role is disruption — Fake Out flinches on turn 1, Parting Shot pivots out while dropping the opponent's Attack and Special Attack, and Intimidate on switch-in compounds that debuff. Max HP / Max SpDef with Careful lets it take special hits reliably. Sitrus Berry extends survivability so it can Parting Shot multiple times in a game. Protect is mandatory in doubles to scout and stall. Speed investment is irrelevant — this Pokemon wants to be slower to control when it uses Parting Shot in Trick Room matchups.</reasoning>
</moveset>

**Garchomp** (fast physical attacker):
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
  <reasoning>Max Speed Jolly is required — dropping speed means opposing Garchomps and Adamant spreads can outpace you, which loses games. Garchompite enables Mega Evolution for greatly increased Attack and Speed. Earthquake and Rock Slide are the core spread damage moves in doubles. Icy Wind provides speed control that lets partners outpace after activation. Protect is mandatory every doubles set — scouting and surviving one turn of pressure is often game-deciding.</reasoning>
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