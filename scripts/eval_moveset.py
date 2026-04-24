"""
Eval runner for moveset_suggest.py.

Runs every Pokemon in the eval dataset through the moveset suggester,
grades each result with code-based and model-based checks, and saves
a timestamped results file so you can track improvement over time.

Usage:
    python scripts/eval_moveset.py
    python scripts/eval_moveset.py --no-model-grade   # code grading only, faster

Model-based (Claude judges Claude, 0–2 per criterion, 8 total):
  - Strategic soundness for doubles
  - Item fits the stated role
  - EV spread logic makes sense
  - Reasoning quality

Code-based (objective, fast):
  - Are all 4 moves in the Champions legal pool?
  - Is the item in the legal items list?
  - Is the ability valid for the species?
  - Do EVs sum to ≤ 510 with no single stat over 252?
  - Valid nature name?
  - Role-specific checks — Incineroar has Fake Out + Parting Shot, Hatterene has Trick Room, etc.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
import click
from rich.console import Console
from rich.table import Table

# Allow importing from scripts/
sys.path.insert(0, str(Path(__file__).parent))
from moveset_suggest import (
    SYSTEM_PROMPT,
    build_user_message,
    load_data,
    name_to_slug,
    parse_response,
    retrieve_rag_context,
)

console = Console()

DATA       = Path(__file__).parents[1] / "data"
MOVES_PATH = DATA / "champions/moves.json"
ABILITIES_PATH = DATA / "champions/abilities.json"
ITEMS_PATH = DATA / "champions/legal_items.json"
DATASET_PATH = DATA / "eval/moveset_eval_dataset.json"
RESULTS_DIR  = DATA / "eval/results"

VALID_NATURES = {
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
}

MODEL_GRADE_PROMPT = """\
You are grading a Pokemon VGC doubles moveset suggestion.
Score each criterion from 0 to 2:
  2 = fully meets the criterion
  1 = partially meets it
  0 = fails it

Respond only with this XML:

<grade>
  <strategic_soundness>
    <score>[0-2]</score>
    <reason>[one sentence]</reason>
  </strategic_soundness>
  <item_role_fit>
    <score>[0-2]</score>
    <reason>[one sentence]</reason>
  </item_role_fit>
  <ev_spread_logic>
    <score>[0-2]</score>
    <reason>[one sentence]</reason>
  </ev_spread_logic>
  <reasoning_quality>
    <score>[0-2]</score>
    <reason>[one sentence]</reason>
  </reasoning_quality>
</grade>
"""


# ── Code-based grading ────────────────────────────────────────────────────────

def code_grade(result: dict, entry: dict, species_slug: str) -> dict[str, bool]:
    moves_data     = json.loads(MOVES_PATH.read_text())
    abilities_data = json.loads(ABILITIES_PATH.read_text())
    items_data     = json.loads(ITEMS_PATH.read_text())

    legal_moves_pool = set(moves_data.get(species_slug, moves_data.get(species_slug.split("-")[0], [])))
    legal_abilities  = set(abilities_data.get(species_slug, abilities_data.get(species_slug.split("-")[0], [])))
    legal_items_set  = set(items_data.get("names", []))

    expect = entry["expect"]
    suggested_moves = set(result["moves"])
    ev_total = sum(result["evs"].values())
    ev_values = list(result["evs"].values())

    checks: dict[str, bool] = {}

    # Core legality
    checks["all_moves_legal"]    = all(m in legal_moves_pool for m in suggested_moves) if suggested_moves else False
    checks["item_legal"]         = result["item"] in legal_items_set
    checks["ability_legal"]      = result["ability"] in legal_abilities if legal_abilities else True
    checks["evs_valid"]          = ev_total <= 510 and all(0 <= v <= 252 for v in ev_values)
    checks["nature_valid"]       = result["nature"] in VALID_NATURES
    checks["four_moves"]         = len(result["moves"]) == 4

    # Role-specific checks from expect
    if expect.get("should_include_protect"):
        checks["has_protect"]        = "Protect" in suggested_moves
    if expect.get("should_include_fake_out"):
        checks["has_fake_out"]       = "Fake Out" in suggested_moves
    if expect.get("should_include_parting_shot"):
        checks["has_parting_shot"]   = "Parting Shot" in suggested_moves
    if expect.get("should_include_trick_room"):
        checks["has_trick_room"]     = "Trick Room" in suggested_moves
    if expect.get("should_include_tailwind"):
        checks["has_tailwind"]       = "Tailwind" in suggested_moves
    if expect.get("has_speed_control"):
        checks["has_speed_control"]  = bool(suggested_moves & {"Tailwind", "Trick Room", "Icy Wind"})
    if expect.get("should_not_max_speed"):
        checks["speed_not_maxed"]    = result["evs"].get("spe", 0) < 252
    if expect.get("should_not_include"):
        illegal = set(expect["should_not_include"])
        checks["no_illegal_moves"]   = not bool(suggested_moves & illegal)
    if expect.get("preferred_items"):
        checks["preferred_item_used"] = result["item"] in expect["preferred_items"]
    if expect.get("preferred_abilities"):
        checks["preferred_ability_used"] = result["ability"] in expect["preferred_abilities"]

    return checks


# ── Model-based grading ───────────────────────────────────────────────────────

def model_grade(species: str, archetype: str, result: dict, client: anthropic.Anthropic) -> dict:
    import re

    ev = result["evs"]
    ev_str = " / ".join(f"{v} {k.upper()}" for k, v in ev.items() if v > 0)
    moveset_text = f"""
Species: {species} ({archetype})
Ability: {result['ability']}
Item: {result['item']}
Nature: {result['nature']}
EVs: {ev_str}
Moves: {', '.join(result['moves'])}
Reasoning: {result['reasoning']}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=MODEL_GRADE_PROMPT,
        messages=[{"role": "user", "content": f"Grade this VGC doubles moveset:\n{moveset_text}"}],
    )

    raw = response.content[0].text
    grades = {}
    for criterion in ["strategic_soundness", "item_role_fit", "ev_spread_logic", "reasoning_quality"]:
        score_match = re.search(rf"<{criterion}>.*?<score>(\d)</score>.*?<reason>(.*?)</reason>", raw, re.DOTALL)
        if score_match:
            grades[criterion] = {
                "score": int(score_match.group(1)),
                "reason": score_match.group(2).strip(),
            }
        else:
            grades[criterion] = {"score": 0, "reason": "parse error"}

    grades["total"] = sum(g["score"] for g in grades.values() if isinstance(g, dict) and "score" in g)
    return grades


# ── Display ───────────────────────────────────────────────────────────────────

def display_results(all_results: list[dict]) -> None:
    table = Table(title="Eval Results", show_lines=True)
    table.add_column("Pokemon", style="bold cyan", width=14)
    table.add_column("Archetype", width=22)
    table.add_column("Code", justify="center", width=8)
    table.add_column("Model", justify="center", width=8)
    table.add_column("Failures")

    for r in all_results:
        code_checks = r["code_grade"]
        total_checks = len(code_checks)
        passed = sum(1 for v in code_checks.values() if v)
        code_str = f"{passed}/{total_checks}"
        code_color = "green" if passed == total_checks else "yellow" if passed >= total_checks * 0.75 else "red"

        model_total = r.get("model_grade", {}).get("total")
        model_str = f"{model_total}/8" if model_total is not None else "—"

        failures = [k for k, v in code_checks.items() if not v]
        fail_str = ", ".join(failures) if failures else "[green]all passed[/green]"

        table.add_row(
            r["species"],
            r["archetype"],
            f"[{code_color}]{code_str}[/{code_color}]",
            model_str,
            fail_str,
        )

    console.print(table)

    # Summary
    all_checks = [v for r in all_results for v in r["code_grade"].values()]
    pct = sum(all_checks) / len(all_checks) * 100 if all_checks else 0
    model_scores = [r["model_grade"]["total"] for r in all_results if r.get("model_grade") and "total" in r["model_grade"]]
    avg_model = sum(model_scores) / len(model_scores) if model_scores else None

    console.print(f"\n[bold]Code grade:[/bold] {pct:.1f}% checks passed")
    if avg_model is not None:
        console.print(f"[bold]Model grade:[/bold] avg {avg_model:.1f}/8 across {len(model_scores)} Pokemon")


# ── Main ──────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--no-model-grade", is_flag=True, help="Skip model-based grading (faster, no API cost)")
def main(no_model_grade: bool) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    dataset = json.loads(DATASET_PATH.read_text())
    client  = anthropic.Anthropic()

    console.print(f"[bold]Running eval on {len(dataset)} Pokemon...[/bold]\n")

    all_results = []

    for entry in dataset:
        species = entry["species"]
        archetype = entry["archetype"]
        console.print(f"[dim]→ {species} ({archetype})[/dim]")

        # Generate moveset
        moves, abilities, items = load_data(species)
        if not moves:
            console.print(f"  [red]No moves found for {species}, skipping[/red]")
            continue

        rag_chunks = retrieve_rag_context(species)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(species, moves, abilities, items, rag_chunks)}],
        )
        result = parse_response(response.content[0].text)

        # Code grading
        slug = name_to_slug(species)
        checks = code_grade(result, entry, slug)

        # Model grading
        model_grades = None
        if not no_model_grade:
            model_grades = model_grade(species, archetype, result, client)
            time.sleep(0.5)

        record = {
            "species":     species,
            "archetype":   archetype,
            "result":      result,
            "code_grade":  checks,
            "model_grade": model_grades,
        }
        all_results.append(record)
        time.sleep(0.3)

    # Save timestamped results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_{timestamp}.json"
    out_path.write_text(json.dumps(all_results, indent=2))
    console.print(f"\n[green]Results saved →[/green] {out_path}\n")

    display_results(all_results)


if __name__ == "__main__":
    main()