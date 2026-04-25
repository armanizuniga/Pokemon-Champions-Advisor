// Main app
const { useState, useMemo, useCallback } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "showFieldDetails": true,
  "compactCards": false,
  "teachingDepth": "balanced",
  "accentHue": 220
}/*EDITMODE-END*/;

function makeMonState(mon) {
  return {
    hp: mon.stats.hp,
    status: "none",
    stages: { atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    volatiles: [],
    teraActive: false
  };
}

function App() {
  const D = window.POKEMON_DATA;

  const [allies] = useState([D.calyrexShadow, D.urshifuRapid]);
  const [opponents] = useState([D.miraidon, D.farigiraf]);

  // Team preview rosters — 6 mons each, including the 2 on field
  const [allyTeam] = useState([
    "Calyrex-Shadow", "Urshifu-Rapid Strike", "Incineroar", "Rillaboom", "Whimsicott", "Amoonguss"
  ]);
  const [opponentTeam] = useState([
    "Miraidon", "Farigiraf", "Iron Hands", "Flutter Mane", "Chien-Pao", "Tornadus"
  ]);

  const [monStates, setMonStates] = useState(() => {
    const s = {};
    [...allies, ...opponents].forEach(m => { s[m.id] = makeMonState(m); });
    return s;
  });

  const [field, setField] = useState({
    weather: "none",
    terrain: "none",
    trickRoom: false,
    gravity: false,
    turn: 1
  });

  const [allySide, setAllySide] = useState({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });
  const [oppSide, setOppSide] = useState({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });

  const [activeAttacker, setActiveAttacker] = useState(allies[0].id);
  const [primaryDefender, setPrimaryDefender] = useState(opponents[0].id);
  const [selectedMove, setSelectedMove] = useState(null);
  const [expandedCards, setExpandedCards] = useState(new Set());

  const [tweaks, setTweaks] = window.useTweaks(TWEAK_DEFAULTS);

  const updateMon = (id, patch) => {
    setMonStates(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  };

  const toggleExpand = (id) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // Compute damage previews from active attacker against the primary defender
  const damagePreviews = useMemo(() => {
    const result = {};
    const allMons = [...allies, ...opponents];
    allMons.forEach(mon => {
      if (mon.id !== activeAttacker) return;
      const attackerState = monStates[mon.id];
      const isAlly = allies.some(a => a.id === mon.id);
      const defender = isAlly
        ? opponents.find(o => o.id === primaryDefender) || opponents[0]
        : allies.find(a => a.id === primaryDefender) || allies[0];
      const defenderState = monStates[defender.id];
      const previews = mon.moves.map(move => {
        return window.calcDamage(mon, defender, move, {
          ...field,
          defenderReflect: isAlly ? oppSide.reflect : allySide.reflect,
          defenderLightScreen: isAlly ? oppSide.lightScreen : allySide.lightScreen
        }, {
          attackerStages: attackerState.stages,
          defenderStages: defenderState.stages,
          attackerTeraActive: attackerState.teraActive,
          attackerTeraType: mon.teraType,
          defenderTeraActive: defenderState.teraActive,
          defenderTeraType: defender.teraType,
          attackerBurned: attackerState.status === "brn",
          defenderHp: defenderState.hp
        });
      });
      result[mon.id] = previews;
    });
    return result;
  }, [activeAttacker, primaryDefender, monStates, field, allySide, oppSide]);

  const buildPrompt = (verbosity) => {
    const monLine = (m, isAlly) => {
      const s = monStates[m.id];
      const stages = Object.entries(s.stages).filter(([, v]) => v !== 0).map(([k, v]) => `${k}${v > 0 ? '+' : ''}${v}`).join(",") || "none";
      return `- ${isAlly ? "ALLY" : "OPP"} ${m.name} (${m.types.join("/")}) | HP ${s.hp}/${m.stats.hp} (${Math.round(s.hp / m.stats.hp * 100)}%) | ${m.ability} | @ ${m.item} | ${m.nature} | Tera: ${m.teraType}${s.teraActive ? " [ACTIVE]" : ""} | Status: ${s.status} | Stages: ${stages} | Volatiles: ${s.volatiles.join(",") || "none"} | Stats ATK/DEF/SPA/SPD/SPE: ${m.stats.atk}/${m.stats.def}/${m.stats.spa}/${m.stats.spd}/${m.stats.spe} | Moves: ${m.moves.map(mv => `${mv.name}(${mv.type}/${mv.category}/${mv.power || "—"}bp)`).join(", ")}`;
    };

    return `You are a top-tier Pokemon VGC doubles coach analyzing a turn. Format Reg G doubles, level 50.

BOARD STATE — TURN ${field.turn}
Weather: ${field.weather} | Terrain: ${field.terrain} | Trick Room: ${field.trickRoom ? "ON" : "off"} | Gravity: ${field.gravity ? "ON" : "off"}
Ally side: Reflect ${allySide.reflect ? "ON" : "off"}, Light Screen ${allySide.lightScreen ? "ON" : "off"}, Tailwind ${allySide.tailwind ? "ON" : "off"}, Stealth Rock ${allySide.stealthRock ? "ON" : "off"}
Opp side: Reflect ${oppSide.reflect ? "ON" : "off"}, Light Screen ${oppSide.lightScreen ? "ON" : "off"}, Tailwind ${oppSide.tailwind ? "ON" : "off"}, Stealth Rock ${oppSide.stealthRock ? "ON" : "off"}

ALLIES:
${allies.map(m => monLine(m, true)).join("\n")}

OPPONENTS:
${opponents.map(m => monLine(m, false)).join("\n")}

Provide a turn analysis. Be ${verbosity === "concise" ? "brief and direct (1-2 sentence sections)" : verbosity === "deep" ? "thorough and educational, explain mechanics" : "balanced — clear recommendations with brief reasoning"}.

Return ONLY JSON in this exact shape (no prose outside the JSON):
{
  "summary": "1-3 sentence read of the board state",
  "threats": [{"from": "PokemonName", "description": "what they likely do and why it's dangerous"}],
  "recommendations": [{"pokemon": "AllyName", "move": "MoveName", "target": "TargetName or 'self'", "reasoning": "why this play", "damage": "rough damage range or KO chance if relevant"}],
  "win_condition": "the path to winning this game",
  "lesson": "${verbosity === "concise" ? "one key takeaway" : "the key VGC concept this turn teaches (positioning, speed control, sack plays, etc)"}"
}`;
  };

  const gameState = { allies, opponents, monStates, field, allySide, oppSide };

  return (
    <div className="app">
      <div className="main-col">
        <div className="topbar">
          <div className="brand">
            <div className="brand-mark"></div>
            <div className="brand-text">
              <div className="brand-name">Champions Advisor</div>
              <div className="brand-tag">VGC DOUBLES · COACHING TOOL</div>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="format-pill"><span className="dot"></span>FORMAT: REG G · L50</span>
            <button className="icon-btn" title="Reset board">↻</button>
          </div>
        </div>

        <div className="battlefield">
          {/* Ally team preview — top left, above side state */}
          <div className="bf-ally-team">
            <window.TeamPreview
              side="ally"
              label="ALLY TEAM"
              roster={allyTeam}
              onField={allies.map(a => a.name)}
            />
          </div>

          {/* Opponent team preview — top right, above side state */}
          <div className="bf-opp-team">
            <window.TeamPreview
              side="opponent"
              label="OPP TEAM"
              roster={opponentTeam}
              onField={opponents.map(o => o.name)}
            />
          </div>

          {/* Ally side state — top left */}
          <div className="bf-ally-side">
            <window.SideStateBar
              side="ally"
              label="ALLY SIDE"
              state={allySide}
              onUpdate={(p) => setAllySide(prev => ({ ...prev, ...p }))}
            />
          </div>

          {/* Opponent side state — top right */}
          <div className="bf-opp-side">
            <window.SideStateBar
              side="opponent"
              label="OPP SIDE"
              state={oppSide}
              onUpdate={(p) => setOppSide(prev => ({ ...prev, ...p }))}
            />
          </div>

          {/* Opponent slot 1 — top right */}
          <div className="bf-opp-slot1">
            <window.PokemonCard
              mon={opponents[0]}
              side="opponent"
              slot={1}
              state={monStates[opponents[0].id]}
              onUpdate={(p) => updateMon(opponents[0].id, p)}
              selectedMoveIdx={activeAttacker === opponents[0].id ? selectedMove : null}
              onSelectMove={(idx) => { setActiveAttacker(opponents[0].id); setSelectedMove(idx); }}
              damagePreviews={damagePreviews[opponents[0].id]}
              expanded={expandedCards.has(opponents[0].id)}
              onToggleExpand={() => toggleExpand(opponents[0].id)}
              isActive={activeAttacker === opponents[0].id}
              onSetActive={() => { setActiveAttacker(opponents[0].id); setPrimaryDefender(allies[0].id); }}
            />
          </div>

          {/* Opponent slot 2 — middle right */}
          <div className="bf-opp-slot2">
            <window.PokemonCard
              mon={opponents[1]}
              side="opponent"
              slot={2}
              state={monStates[opponents[1].id]}
              onUpdate={(p) => updateMon(opponents[1].id, p)}
              selectedMoveIdx={activeAttacker === opponents[1].id ? selectedMove : null}
              onSelectMove={(idx) => { setActiveAttacker(opponents[1].id); setSelectedMove(idx); }}
              damagePreviews={damagePreviews[opponents[1].id]}
              expanded={expandedCards.has(opponents[1].id)}
              onToggleExpand={() => toggleExpand(opponents[1].id)}
              isActive={activeAttacker === opponents[1].id}
              onSetActive={() => { setActiveAttacker(opponents[1].id); setPrimaryDefender(allies[0].id); }}
            />
          </div>

          {/* Field bar — center column */}
          <div className="bf-field">
            <window.FieldBar field={field} onUpdate={(p) => setField(prev => ({ ...prev, ...p }))} />
          </div>

          {/* Ally slot 1 — middle left */}
          <div className="bf-ally-slot1">
            <window.PokemonCard
              mon={allies[0]}
              side="ally"
              slot={1}
              state={monStates[allies[0].id]}
              onUpdate={(p) => updateMon(allies[0].id, p)}
              selectedMoveIdx={activeAttacker === allies[0].id ? selectedMove : null}
              onSelectMove={(idx) => { setActiveAttacker(allies[0].id); setSelectedMove(idx); }}
              damagePreviews={damagePreviews[allies[0].id]}
              expanded={expandedCards.has(allies[0].id)}
              onToggleExpand={() => toggleExpand(allies[0].id)}
              isActive={activeAttacker === allies[0].id}
              onSetActive={() => { setActiveAttacker(allies[0].id); setPrimaryDefender(opponents[0].id); }}
            />
          </div>

          {/* Ally slot 2 — bottom left */}
          <div className="bf-ally-slot2">
            <window.PokemonCard
              mon={allies[1]}
              side="ally"
              slot={2}
              state={monStates[allies[1].id]}
              onUpdate={(p) => updateMon(allies[1].id, p)}
              selectedMoveIdx={activeAttacker === allies[1].id ? selectedMove : null}
              onSelectMove={(idx) => { setActiveAttacker(allies[1].id); setSelectedMove(idx); }}
              damagePreviews={damagePreviews[allies[1].id]}
              expanded={expandedCards.has(allies[1].id)}
              onToggleExpand={() => toggleExpand(allies[1].id)}
              isActive={activeAttacker === allies[1].id}
              onSetActive={() => { setActiveAttacker(allies[1].id); setPrimaryDefender(opponents[0].id); }}
            />
          </div>

        </div>
      </div>

      <div className="side-col">
        <window.AnalysisPanel buildPrompt={buildPrompt} gameState={gameState} />
      </div>

      {/* Tweaks Panel */}
      <window.TweaksPanel title="Tweaks">
        <window.TweakSection title="Display">
          <window.TweakToggle
            label="Compact cards"
            value={tweaks.compactCards}
            onChange={(v) => setTweaks({ compactCards: v })}
          />
          <window.TweakToggle
            label="Show field details"
            value={tweaks.showFieldDetails}
            onChange={(v) => setTweaks({ showFieldDetails: v })}
          />
        </window.TweakSection>
        <window.TweakSection title="Coaching">
          <window.TweakRadio
            label="Teaching depth"
            value={tweaks.teachingDepth}
            options={["concise", "balanced", "deep"]}
            onChange={(v) => setTweaks({ teachingDepth: v })}
          />
        </window.TweakSection>
        <window.TweakSection title="Theme">
          <window.TweakSlider
            label="Accent hue"
            value={tweaks.accentHue}
            min={0} max={360} step={5}
            onChange={(v) => {
              setTweaks({ accentHue: v });
              document.documentElement.style.setProperty("--ally", `oklch(0.78 0.16 ${v})`);
              document.documentElement.style.setProperty("--ally-dim", `oklch(0.78 0.16 ${v} / 0.15)`);
            }}
          />
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
