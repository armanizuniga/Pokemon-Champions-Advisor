# Handoff: VGC Battle Assistant

## Overview
A real-time competitive Pokémon (VGC / Reg G doubles) decision-support tool. The user inputs the live state of a 2v2 battle — both teams' Pokémon, HP, status conditions, stat stages, field effects (weather/terrain/screens/etc.), and the current turn — and the app produces:

1. **Live damage previews** for the active attacker's moves vs. the primary defender, accounting for STAB, type effectiveness, item, ability, weather/terrain, screens, spread reduction, burn, and Tera.
2. **A "Send to Claude" analysis flow** that submits the full battle state to an LLM and renders structured strategic output: situation summary, top threats, recommended actions per ally, win condition, and a "lesson" for player improvement.

The UI is a single-screen dashboard styled after Pokémon Champions' purple/lime visual language while preserving an analytical, dense, calc-tool aesthetic.

## About the Design Files
The files in `design_files/` are **design references created in HTML + React + Babel inline** — interactive prototypes showing the intended look, layout, and behavior. They are **not production code to ship directly**.

The task is to **recreate these designs in the target codebase's existing environment** (React, Vue, SwiftUI, native, etc.) using its established component patterns, state management, routing, and styling conventions. If no environment exists yet, choose the most appropriate framework and implement there.

The included `data/calc.js` is a **simplified Gen 9 damage calculator** suitable as a reference for the formula shape and modifier ordering, but production should use a vetted library like [`@smogon/calc`](https://github.com/smogon/damage-calc) for full accuracy (critical hits, all abilities, all items, multi-hit moves, weather/terrain interactions, etc.).

## Fidelity
**High-fidelity (hifi).** The mocks are pixel-precise on colors, spacing, typography, and interaction states. Recreate the visual treatment exactly — purple panels, lime-green selected/active states, pill-shaped controls, type-colored circular move badges. Adjust to match the host codebase's component primitives where they exist.

---

## Screens / Views

There is **one main screen** with three regions in a 3-column layout:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Topbar: turn counter • field weather/terrain pill • "Submit" button   │
├──────────────┬─────────────────────────────────────────┬────────────────┤
│              │                                         │                │
│  Left rail   │           Battlefield                   │  Right rail    │
│  (collapsed  │  ┌──────────┬──────────┬──────────┐    │  Claude        │
│  field state │  │ Ally     │  Field   │ Opp team │    │  Analysis      │
│  controls)   │  │ team     │  bar     │ preview  │    │  Panel         │
│              │  │ preview  │          │          │    │                │
│              │  ├──────────┼──────────┼──────────┤    │                │
│              │  │ Ally     │          │ Opp      │    │                │
│              │  │ side     │          │ side     │    │                │
│              │  │ state    │          │ state    │    │                │
│              │  ├──────────┤          ├──────────┤    │                │
│              │  │ Ally     │          │ Opp      │    │                │
│              │  │ Slot 1   │          │ Slot 1   │    │                │
│              │  ├──────────┤          ├──────────┤    │                │
│              │  │ Ally     │          │ Opp      │    │                │
│              │  │ Slot 2   │          │ Slot 2   │    │                │
│              │  └──────────┴──────────┴──────────┘    │                │
│              │                                         │                │
└──────────────┴─────────────────────────────────────────┴────────────────┘
```

### Top Bar
- **Turn counter** (left): a glowing lime-green pill with `TURN` label and large number, with `−` / `+` buttons to step turns.
- **Field summary** (center): shows current weather + terrain at a glance.
- **Submit button** (right): chunky lime-green pill with "SEND TO CLAUDE" text. Triggers analysis.

### Battlefield (center column)
A 4-row × 3-col CSS grid. The field-bar in the middle column spans rows 3–4 (the two slot rows).

**Row 1 — Team Previews**
- Two cards (`<TeamPreview>`), one per side. Each shows 6 mon names as pills.
- Mons currently on the field are highlighted with the lime active treatment (lime fill, dark text, glow).
- Bench mons are dim with a small grey dot.
- Centered label above the pill row: "ALLY TEAM" / "OPP TEAM".

**Row 2 — Side State Strips**
- Pill-row of 4 toggles per side: `Reflect`, `L. Screen`, `Tailwind`, `S. Rock`.
- Toggles use the lime active style with a small leading dot.

**Rows 3–4 — Pokémon Cards (2 per side, slot 1 above slot 2)**

Each `<PokemonCard>` displays:
- **Header**: active toggle (lime ring + dot when on-field), sprite/icon placeholder, **name**, level pill, gender, item, ability, **dual type badges**, Tera type label.
- **HP bar**: rounded pill, green→orange→red gradient, glow; numeric `current / max` and `%`.
- **Quick stats grid** (4 cells): item • ability • status select • Tera button.
- **Status select**: pill dropdown — `—`, `BRN`, `PAR`, `PSN`, `TOX`, `SLP`, `FRZ`. Each color-coded.
- **Stat cells (6)**: HP / ATK / DEF / SPA / SPD / SPE — show numeric value + a thin bar fill at the bottom indicating relative strength.
- **Moves list (4)**: each move row is a horizontal pill with:
  - Circular type-colored badge on the left (20×20px)
  - Move name
  - Type badge (small)
  - PHY/SPE/STA category tag, base power, accuracy, PP
  - When this card is the active attacker, a damage preview row showing `min%–max%` damage, effectiveness tag (`SE`/`NVE`/`IMM`), and KO chance pill (`OHKO`/`KO?`)
  - **Selected state**: pill expands to a 14px-radius rounded rect, lime border + lime-soft fill + lime glow.
- **Expandable advanced controls** (accordion):
  - Stat-stage controls: 6 columns of `+`/`−` steppers with current stage value, range −6 to +6.
  - Tera toggle button.
  - Volatile chips: `Confused`, `Taunted`, `Encored`, `Charged`, `Substitute`, etc.

### Field Bar (center column, spans slot rows)
A vertical pill-bar `<FieldBar>`:
- **Weather** segment: `None` / `Sun` / `Rain` / `Sand` / `Snow` (radio).
- **Terrain** segment: `None` / `Electric` / `Grassy` / `Psychic` / `Misty` (radio).
- **Trick Room** toggle (pill).
- **Gravity** toggle (pill).
- All toggles use the lime active treatment.

### Right Rail — Analysis Panel
`<AnalysisPanel>`:
- **Idle state**: empty placeholder with prompt "Submit battle state to get strategic analysis."
- **Loading state**: spinner + "Claude is analyzing..."
- **Result state** (rendered from JSON returned by Claude):
  - **Summary**: 1–2 sentence situation read.
  - **Threats** (list): each threat is an enemy-tinted card with mon name, threat description, and danger level.
  - **Recommendations** (per ally): ally-tinted card with the ally name, recommended move/action, target, expected damage range pill (lime).
  - **Win Condition**: one-line goal statement.
  - **Lesson**: short coaching takeaway for player improvement.

### Left Rail
Collapsed/secondary controls (currently minimal — primary field state is in the center field-bar). Reserved for future expansion (team builder, replay history, etc.).

---

## Interactions & Behavior

### Selection model
- Exactly one **active attacker** at a time (clicking a card's active-toggle dot promotes it).
- Exactly one **primary defender** (auto-set to opposing slot 1 unless overridden by clicking an opponent card).
- Selecting a move on the active attacker's card highlights it lime and locks it in for analysis submission.

### Live damage preview
Whenever attacker, defender, move, field, or any mon state changes, recompute and re-render move rows' damage chips.

`calcDamage(attacker, defender, move, field, opts)` → `{ min, max, minPct, maxPct, koChance, effectiveness }`.

`opts` includes: `attackerStages`, `defenderStages`, `attackerTeraActive`, `attackerTeraType`, `defenderTeraActive`, `defenderTeraType`, `attackerBurned`, `attackerAirborne`, `defenderAirborne`, `crit`.

### Submit to Claude
On submit:
1. Build a JSON payload of full battle state (see schema below).
2. Call `claude.complete(messages)` (or your backend's LLM endpoint).
3. Parse JSON response into the analysis schema; render in right rail.
4. Show loading spinner during round-trip; show error state on failure.

### Animations & transitions
- Card border-color, box-shadow: 150ms ease.
- HP bar width: 300ms ease.
- Active toggle dot: 150ms.
- Move row hover: 120ms.
- Lime glow uses `box-shadow: 0 0 12px var(--lime-glow)`.

---

## State Management

### Top-level state
```ts
{
  allies: Pokemon[2],          // immutable roster of on-field allies
  opponents: Pokemon[2],       // immutable roster of on-field opponents
  allyTeam: string[6],         // team preview names
  opponentTeam: string[6],     // team preview names

  monStates: { [monId]: MonState },  // mutable per-mon state

  field: {
    weather: "none" | "sun" | "rain" | "sand" | "snow",
    terrain: "none" | "electric" | "grassy" | "psychic" | "misty",
    trickRoom: boolean,
    gravity: boolean,
    turn: number
  },

  allySide:  { reflect: bool, lightScreen: bool, tailwind: bool, stealthRock: bool },
  oppSide:   { reflect: bool, lightScreen: bool, tailwind: bool, stealthRock: bool },

  activeAttacker: monId,
  primaryDefender: monId,
  selectedMove: Move | null,
  expandedCards: Set<monId>,

  analysis: { status: "idle" | "loading" | "result" | "error", data?: AnalysisResult }
}
```

### Pokemon shape
```ts
{
  id: string,
  name: string,
  types: [Type, Type?],
  ability: string,
  item: string,
  nature: string,
  teraType: Type,
  level: 50,
  gender: "♂" | "♀" | "—",
  baseStats: { hp, atk, def, spa, spd, spe },
  evs:       { hp, atk, def, spa, spd, spe },  // 0–252, total ≤ 508
  ivs:       { hp, atk, def, spa, spd, spe },  // 0–31
  stats:     { hp, atk, def, spa, spd, spe },  // computed at level
  moves: Move[4]
}
```

### Move shape
```ts
{
  name: string,
  type: Type,
  category: "Physical" | "Special" | "Status",
  power: number,           // 0 for status
  acc: number,             // 0–100
  pp: number,
  target: "single" | "all-foes" | "self" | "ally",
  desc: string
}
```

### MonState shape (mutable per-mon)
```ts
{
  hp: number,
  status: "none" | "brn" | "par" | "psn" | "tox" | "slp" | "frz",
  stages: { atk: -6..+6, def: -6..+6, spa: -6..+6, spd: -6..+6, spe: -6..+6 },
  volatiles: string[],     // ["confused", "taunted", "encored", ...]
  teraActive: boolean
}
```

### Claude analysis payload (submit)
```json
{
  "turn": 4,
  "field": { "weather": "sun", "terrain": "none", "trickRoom": false, "gravity": false },
  "allySide": { "reflect": false, "lightScreen": true, "tailwind": false, "stealthRock": false },
  "oppSide":  { "reflect": false, "lightScreen": false, "tailwind": true, "stealthRock": true },
  "allies":     [ /* full Pokemon + MonState */ ],
  "opponents":  [ /* full Pokemon + MonState */ ],
  "selectedMove": { "by": "calyrexShadow", "move": "Astral Barrage" }
}
```

### Claude analysis response (render)
```json
{
  "summary": "string, 1–2 sentences",
  "threats": [
    { "mon": "Miraidon", "level": "high|med|low", "note": "string" }
  ],
  "recommendations": [
    { "ally": "Calyrex-Shadow", "move": "Astral Barrage", "target": "both", "dmgRange": "62–73%", "rationale": "string" }
  ],
  "win_condition": "string",
  "lesson": "string"
}
```

---

## Design Tokens

### Colors
```css
--bg:            #1d1342;   /* deep violet outer */
--bg-2:          #2a1d5c;
--surface:       #3a2980;   /* main panel violet */
--surface-alt:   #2e2068;
--surface-2:     #4a3596;
--surface-3:     #5640a8;
--border:        #7a5fd6;
--border-soft:   #4e3a9a;
--border-strong: #9b86e8;

--text:          #ffffff;
--text-dim:      #c9beea;
--text-faint:    #8b7fc0;

--ally:          #5fb0ff;   /* P1 blue accent */
--ally-bg:       #2c4d8a;
--ally-soft:     #344a78;
--enemy:         #ff6b7a;   /* P2 red accent */
--enemy-bg:      #8a2c3c;
--enemy-soft:    #6e2638;

--lime:          #c8ff3d;   /* Champions signature highlight */
--lime-glow:     #a8e828;
--lime-soft:     #2f4a1f;

--good:          #4ad96a;   /* HP > 50% */
--warn:          #ffc14d;   /* HP 20–50% */
--bad:           #ff5566;   /* HP < 20% */
--accent:        #ffd84d;   /* gold */
```

Background uses two radial gradients layered on `--bg`:
```css
background:
  radial-gradient(ellipse at top left,    #3a1d6a 0%, transparent 50%),
  radial-gradient(ellipse at bottom right,#4a2a8a 0%, transparent 50%),
  var(--bg);
background-attachment: fixed;
```

### Type colors
See `data/pokemon.js` `window.TYPE_COLORS` — standard Pokémon type palette (Fire `#ee8130`, Water `#6390f0`, Grass `#7ac74c`, Electric `#f7d02c`, Ghost `#735797`, Psychic `#f95587`, etc.).

### Spacing
- Card padding: `10px 11px`
- Panel padding: `7px 10px` to `12px 10px`
- Gap (small): 4–6px
- Gap (medium): 8px
- Gap (large): 12px

### Typography
- Family: `'Inter', system-ui, -apple-system, sans-serif`
- Mono: `'JetBrains Mono', monospace` (for stat numbers, move meta, KO chips, labels)
- Base size: `12.5px / 1.4`
- Stat values: `12px 700`
- Stat labels: `7.5px 700` letter-spaced 0.06em
- Move name: `11px 600`
- Move meta: `9.5–10px mono`
- Turn number: `22px 800 -0.02em`
- Submit button: `11.5px 800 0.06em uppercase`

### Border radius
- Pill: `99px` (toggles, badges, stat select, move rows non-selected, team mons)
- Card: `14px` (panels, selected move row, side-state, team-preview, topbar)
- Inner controls: `10px` (advanced-controls bg, stage-ctrl)
- Small: `8px` (stat cells, stage buttons)

### Shadows
- Panel drop: `0 2px 0 rgba(0,0,0,0.2)` (dark crisp under-shadow)
- Active glow: `0 0 0 2px var(--lime), 0 0 16px -2px var(--lime-glow)`
- Lime glow: `0 0 8–12px var(--lime-glow)`
- HP bar fill: `0 0 6px -1px currentColor`

---

## Assets
- **Type colors**: `window.TYPE_COLORS` in `data/pokemon.js` (standard 18-type palette).
- **Pokémon sprites/icons**: not bundled. Production should pull from PokéAPI sprite CDN (`https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/`) or the host app's existing asset pipeline.
- **Fonts**: Google Fonts `Inter` and `JetBrains Mono` (load via `@import` or `<link>`).
- **Reference screenshots**: The visual style was matched against Pokémon Champions UI (purple panels, lime selection, rounded pills). See user-provided screenshots in the conversation history for source inspiration.

---

## Files

```
design_files/
├── index.html                       # Entry point — script tags + root mount
├── app.jsx                          # Top-level App component, state, layout grid
├── styles.css                       # All visual treatment (variables, layout, components)
├── tweaks-panel.jsx                 # Optional in-design tweak controls
├── components/
│   ├── pokemon-card.jsx             # PokemonCard + MoveRow + StatStageControl + StatusSelect
│   ├── field-bar.jsx                # Vertical weather/terrain/room toggles
│   ├── team-preview.jsx             # 6-mon roster pill row per side
│   └── analysis-panel.jsx           # Claude analysis idle/loading/result/error states
└── data/
    ├── pokemon.js                   # Sample Reg G mons + TYPE_COLORS + TYPE_CHART
    └── calc.js                      # Simplified Gen 9 damage calculator
```

### Key files to read first
1. `app.jsx` — overall layout grid + state shape (lines 1–80 cover the App component setup).
2. `styles.css` — `:root` tokens at top, then layout grid (`.battlefield`), then component styles.
3. `components/pokemon-card.jsx` — most complex component, drives the move/stat/stage UI.
4. `data/calc.js` — shows the modifier ordering for damage. Replace with `@smogon/calc` in production.

### Production library recommendations
- **Damage calc**: [`@smogon/calc`](https://www.npmjs.com/package/@smogon/calc) — battle-tested, full Gen 9 support.
- **Pokémon data**: [`pokedex-promise-v2`](https://www.npmjs.com/package/pokedex-promise-v2) for PokéAPI access, or [`@pkmn/dex`](https://www.npmjs.com/package/@pkmn/dex) for Showdown's data.
- **Sprites**: [`@pkmn/img`](https://www.npmjs.com/package/@pkmn/img) for stylized sprite components.
- **LLM**: Anthropic SDK (`@anthropic-ai/sdk`) — match the analysis JSON schema above in your system prompt.
