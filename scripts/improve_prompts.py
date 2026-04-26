"""
Improve system prompts using expert VGC knowledge from ChromaDB transcripts.

Multi-pass approach to stay under the 30k input token/minute API limit:
  Pass 1 (5 calls): Query ChromaDB by topic batch → mini-summary per batch
  Pass 2 (1 call):  Synthesize all mini-summaries → master expert knowledge doc
  Pass 3 (1 call):  Master doc + current prompts → improved prompts

Output saved to data/prompt_improvements/<timestamp>/

Usage:
    python scripts/improve_prompts.py
"""

import re
import time
from datetime import datetime
from pathlib import Path

import anthropic
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

console = Console()

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parents[1]
DATA          = ROOT / "data"
CHROMADB_PATH = DATA / "chromadb"
OUTPUT_DIR    = DATA / "prompt_improvements"
MOVESET_SCRIPT  = ROOT / "scripts/moveset_suggest.py"
PREVIEW_SCRIPT  = ROOT / "scripts/team_preview.py"
ADVISOR_SCRIPT  = ROOT / "backend/advisor.py"
CLAUDE_MD       = ROOT / "CLAUDE.md"
KNOWLEDGE_BASE  = ROOT / "data/VGC_Pokemon_Champions_Knowledge_Base.md"

CHUNKS_PER_QUERY = 3
SLEEP_BETWEEN_BATCHES = 13  # seconds — keeps Pass 1 well under 30k tokens/min

# ── Topic batches for Pass 1 ──────────────────────────────────────────────────

TOPIC_BATCHES = [
    {
        "name": "Speed Tiers & Turn Order",
        "queries": [
            "speed tier priority outspeeding doubles VGC max speed investment",
            "trick room setup slow team when to use priority bracket",
            "tailwind turns speed control doubles strategy duration",
            "speed creep EV mirrors edge out same base speed tie priority moves",
        ],
    },
    {
        "name": "Team Preview & Win Conditions",
        "queries": [
            "team preview lead selection which four to bring win condition",
            "reading opponent gameplan archetype team synergy doubles",
            "lead pair opener pressure game plan first turn doubles",
            "back pair rescue bad matchup team preview decision",
        ],
    },
    {
        "name": "EV Benchmarks & Damage Thresholds",
        "queries": [
            "EV spread specific damage benchmark survive KO threshold doubles",
            "bulk investment HP defense tradeoff offensive EV spread",
            "damage calc benchmark OHKO 2HKO specific numbers doubles",
            "EV spread targeting outspeeding benchmark nature modifier",
        ],
    },
    {
        "name": "Items, Abilities & Mega Slots",
        "queries": [
            "choice scarf focus sash item role doubles when to use",
            "mega evolution team building slot commitment stone doubles",
            "intimidate prankster ability doubles competitive usage",
            "berry leftovers shell bell item doubles bulk recovery",
        ],
    },
    {
        "name": "Field Control, Weather & Terrain",
        "queries": [
            "Protect doubles mandatory mechanics scouting redirection follow me",
            "weather rain sun sand snow doubles field effect strategy",
            "terrain electric psychic grassy misty doubles competitive",
            "status burn paralysis doubles spread moves field control",
        ],
    },
]

# ── ChromaDB ──────────────────────────────────────────────────────────────────

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


def query_batch(queries: list[str]) -> list[str]:
    """Run all queries across both collections, return deduplicated chunks."""
    seen   = set()
    chunks = []
    for query in queries:
        for cname in ("vgc_transcripts", "vgc_web"):
            col = _get_collection(cname)
            if col is None or col.count() == 0:
                continue
            results = col.query(
                query_texts=[query],
                n_results=CHUNKS_PER_QUERY,
                include=["documents", "metadatas"],
            )
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                if doc not in seen:
                    seen.add(doc)
                    chunks.append(_format_chunk(doc, meta))
    return chunks


# ── Prompt extraction ─────────────────────────────────────────────────────────

def extract_system_prompt(script_path: Path) -> str:
    src = script_path.read_text()
    m = re.search(r'SYSTEM_PROMPT = """\\?\n?(.*?)"""', src, re.DOTALL)
    return m.group(1).strip() if m else ""


# ── Claude calls ──────────────────────────────────────────────────────────────

client = anthropic.Anthropic()


def distill_batch(batch_name: str, chunks: list[str]) -> str:
    """Pass 1: distill a topic batch into a compact mini-summary."""
    chunk_text = "\n\n---\n\n".join(chunks)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                f"You are extracting expert VGC doubles strategy insights from player commentary.\n\n"
                f"Topic: {batch_name}\n\n"
                f"<transcripts>\n{chunk_text}\n</transcripts>\n\n"
                "Extract the most actionable insights from these transcripts into 6-10 concise bullet points. "
                "Focus on specific numbers, thresholds, and decision rules — not vague advice. "
                "Only include insights actually supported by the text."
            ),
        }],
    )
    return response.content[0].text


def synthesize_knowledge(batch_summaries: dict[str, str]) -> str:
    """Pass 2: synthesize all mini-summaries into a master expert knowledge doc."""
    summaries_text = "\n\n".join(
        f"## {name}\n{summary}" for name, summary in batch_summaries.items()
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": (
                "You are synthesizing expert VGC doubles strategy knowledge.\n\n"
                "Below are summaries of insights extracted from hours of top player commentary, "
                "organized by topic.\n\n"
                f"{summaries_text}\n\n"
                "Synthesize these into a single cohesive expert knowledge document. "
                "Organize by theme, eliminate redundancy, and preserve all specific numbers and rules. "
                "This document will be used to improve AI system prompts for a VGC advisor tool."
            ),
        }],
    )
    return response.content[0].text


def improve_prompts(master_knowledge: str, moveset_prompt: str, preview_prompt: str, advisor_prompt: str, claude_md: str, knowledge_base: str) -> str:
    """Pass 3: rewrite all three system prompts using the master knowledge doc + Champions knowledge base."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        messages=[{
            "role": "user",
            "content": (
                "You are improving AI system prompts for a Pokemon VGC advisor tool.\n\n"
                "## Project Context\n"
                f"{claude_md}\n\n"
                "## Pokémon Champions Knowledge Base (authoritative format reference)\n"
                "<knowledge_base>\n"
                f"{knowledge_base}\n"
                "</knowledge_base>\n\n"
                "## Expert Knowledge (synthesized from top player transcripts)\n"
                f"{master_knowledge}\n\n"
                "## Current Moveset Suggestion Prompt\n"
                f"<moveset_prompt>\n{moveset_prompt}\n</moveset_prompt>\n\n"
                "## Current Team Preview Prompt\n"
                f"<preview_prompt>\n{preview_prompt}\n</preview_prompt>\n\n"
                "## Current Battle Advisor Prompt (turn-by-turn mid-battle analysis)\n"
                f"<advisor_prompt>\n{advisor_prompt}\n</advisor_prompt>\n\n"
                "Using both the knowledge base (Champions-specific rules, items, abilities, game changes) "
                "and the expert knowledge (synthesized player strategy), rewrite all three prompts to be more "
                "accurate and grounded. Prioritize the knowledge base for factual correctness (what is and "
                "isn't in the game), and the expert knowledge for strategic depth. "
                "For each change, briefly note what drove it.\n\n"
                "Output exactly:\n"
                "<improved_moveset_prompt>\n[full improved prompt]\n</improved_moveset_prompt>\n\n"
                "<improved_preview_prompt>\n[full improved prompt]\n</improved_preview_prompt>\n\n"
                "<improved_advisor_prompt>\n[full improved prompt]\n</improved_advisor_prompt>\n\n"
                "<change_log>\n[bullet points: what changed in each prompt and what drove it]\n</change_log>"
            ),
        }],
    )
    return response.content[0].text


# ── Output helpers ────────────────────────────────────────────────────────────

def extract_tag(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def save_outputs(batch_summaries: dict, master_knowledge: str, raw_response: str, timestamp: str):
    out = OUTPUT_DIR / timestamp
    out.mkdir(parents=True, exist_ok=True)

    (out / "batch_summaries.md").write_text(
        "\n\n".join(f"## {k}\n{v}" for k, v in batch_summaries.items())
    )
    (out / "master_knowledge.md").write_text(master_knowledge)

    moveset = extract_tag(raw_response, "improved_moveset_prompt")
    preview = extract_tag(raw_response, "improved_preview_prompt")
    advisor = extract_tag(raw_response, "improved_advisor_prompt")
    changes = extract_tag(raw_response, "change_log")

    if moveset:
        (out / "improved_moveset_prompt.txt").write_text(moveset)
    if preview:
        (out / "improved_preview_prompt.txt").write_text(preview)
    if advisor:
        (out / "improved_advisor_prompt.txt").write_text(advisor)
    if changes:
        (out / "change_log.md").write_text(changes)

    return out, moveset, preview, advisor, changes


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    console.print(Rule("[bold]Prompt Improvement Pipeline[/bold]"))
    transcripts = _get_collection("vgc_transcripts")
    web         = _get_collection("vgc_web")
    total_chunks = (transcripts.count() if transcripts else 0) + (web.count() if web else 0)
    console.print(f"[dim]ChromaDB chunks available: {total_chunks} (transcripts + web)[/dim]\n")

    # ── Pass 1: distill topic batches ─────────────────────────────────────────
    console.print("[bold cyan]Pass 1[/bold cyan] — Extracting insights by topic batch\n")
    batch_summaries = {}

    for i, batch in enumerate(TOPIC_BATCHES):
        console.print(f"  Batch {i+1}/5: [bold]{batch['name']}[/bold]", end=" ")
        chunks = query_batch(batch["queries"])
        console.print(f"[dim]({len(chunks)} chunks)[/dim]", end=" ")
        summary = distill_batch(batch["name"], chunks)
        batch_summaries[batch["name"]] = summary
        console.print("[green]✓[/green]")

        if i < len(TOPIC_BATCHES) - 1:
            console.print(f"  [dim]Waiting {SLEEP_BETWEEN_BATCHES}s...[/dim]")
            time.sleep(SLEEP_BETWEEN_BATCHES)

    # ── Pass 2: synthesize master knowledge doc ───────────────────────────────
    console.print(f"\n[bold cyan]Pass 2[/bold cyan] — Synthesizing master knowledge document", end=" ")
    master_knowledge = synthesize_knowledge(batch_summaries)
    console.print("[green]✓[/green]")

    # ── Pass 3: improve prompts ───────────────────────────────────────────────
    console.print(f"\n[bold cyan]Pass 3[/bold cyan] — Rewriting system prompts", end=" ")
    moveset_prompt   = extract_system_prompt(MOVESET_SCRIPT)
    preview_prompt   = extract_system_prompt(PREVIEW_SCRIPT)
    advisor_prompt   = extract_system_prompt(ADVISOR_SCRIPT)
    claude_md_text   = CLAUDE_MD.read_text()
    knowledge_base   = KNOWLEDGE_BASE.read_text() if KNOWLEDGE_BASE.exists() else ""

    if knowledge_base:
        console.print(f"[dim](+knowledge base)[/dim]", end=" ")

    raw_response = improve_prompts(master_knowledge, moveset_prompt, preview_prompt, advisor_prompt, claude_md_text, knowledge_base)
    console.print("[green]✓[/green]\n")

    # ── Save & display ────────────────────────────────────────────────────────
    out_dir, moveset, preview, advisor, changes = save_outputs(
        batch_summaries, master_knowledge, raw_response, timestamp
    )

    console.print(Panel(changes or raw_response, title="[bold]Change Log[/bold]", border_style="green"))
    console.print(f"\n[dim]Outputs saved to {out_dir}/[/dim]")
    console.print("[dim]Files: improved_moveset_prompt.txt, improved_preview_prompt.txt, improved_advisor_prompt.txt[/dim]")
    console.print("[dim]Review the files, then manually apply changes to the scripts.[/dim]")


if __name__ == "__main__":
    main()