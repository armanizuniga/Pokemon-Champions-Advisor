# Champions Advisor — Frontend

React + Vite battle dashboard for the Pokémon Champions VGC Advisor.

## Dev

```bash
npm install
npm run dev        # http://localhost:5173
```

Requires the backend running on port 8000 — see root README.

## Structure

```
src/
  App.jsx                   # Top-level state and layout
  index.css                 # All styles (Champions purple/lime design tokens)
  components/
    PokemonCard.jsx          # Per-Pokémon card: HP, moves, stats, stage controls
    FieldBar.jsx             # Center column: turn, weather, terrain, rooms
    TeamPreview.jsx          # 6-mon roster pill row with on-field highlights
    AnalysisPanel.jsx        # Right rail: submit + render Claude analysis
    TypeBadge.jsx            # Type-colored inline badge
    MoveRow.jsx              # Move pill with category/power/acc/pp
  data/
    typeColors.js            # 18-type color palette
    initialState.js          # Example battle state (Garchomp+Incineroar vs Torkoal+Venusaur)
```

## API

Calls `POST /api/analyze` — proxied to `http://localhost:8000` by Vite.
Response shape: `{ recommendation: { action_1, action_2, priority_order, threat_assessment, contingency, reasoning }, damage_matrix: [...] }`
