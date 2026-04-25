import { useState, useCallback } from 'react';
import TeamPreview from './components/TeamPreview';
import FieldBar, { SideStateBar } from './components/FieldBar';
import PokemonCard from './components/PokemonCard';
import AnalysisPanel from './components/AnalysisPanel';
import {
  INITIAL_ALLIES, INITIAL_OPPONENTS,
  INITIAL_ALLY_TEAM, INITIAL_OPP_TEAM,
  INITIAL_BACK, makeMonState,
} from './data/initialState';

function initMonStates(mons) {
  const s = {};
  mons.forEach(m => { s[m.id] = makeMonState(m); });
  return s;
}

export default function App() {
  const [allies]    = useState(INITIAL_ALLIES);
  const [opponents] = useState(INITIAL_OPPONENTS);

  const [monStates, setMonStates] = useState(() =>
    initMonStates([...INITIAL_ALLIES, ...INITIAL_OPPONENTS])
  );

  const [field, setField] = useState({
    weather: 'sun', terrain: 'none', trickRoom: false, gravity: false, turn: 1,
  });

  const [allySide, setAllySide] = useState(
    { reflect: false, lightScreen: false, tailwind: false, stealthRock: false }
  );
  const [oppSide, setOppSide] = useState(
    { reflect: false, lightScreen: false, tailwind: false, stealthRock: false }
  );

  const [activeAttacker, setActiveAttacker] = useState(allies[0].id);
  const [selectedMove,   setSelectedMove]   = useState(null);

  const updateMon = useCallback((id, patch) => {
    setMonStates(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }, []);

  function resetBoard() {
    setMonStates(initMonStates([...INITIAL_ALLIES, ...INITIAL_OPPONENTS]));
    setField({ weather: 'sun', terrain: 'none', trickRoom: false, gravity: false, turn: 1 });
    setAllySide({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });
    setOppSide({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });
    setSelectedMove(null);
  }

  const buildPayload = useCallback(() => {
    const monToPayload = (mon, state) => ({
      species:    mon.name,
      hp_percent: state.hp / mon.stats.hp,
      item:       mon.item || null,
      ability:    mon.ability || null,
      status:     state.status !== 'none' ? state.status : null,
      boosts:     state.stages,
      moves:      mon.moves.map(m => m.name),
    });

    const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

    return {
      turn:            field.turn,
      your_active:     allies.map(m => monToPayload(m, monStates[m.id])),
      opponent_active: opponents.map(m => monToPayload(m, monStates[m.id])),
      your_back:       INITIAL_BACK.ally.map(b => ({ species: b.name, hp_percent: b.hpPercent })),
      opponent_back:   INITIAL_BACK.opp.map(b => ({ species: b.name, hp_percent: b.hpPercent })),
      field: {
        weather:                field.weather !== 'none' ? cap(field.weather) : null,
        terrain:                field.terrain !== 'none' ? cap(field.terrain) : null,
        trick_room:             field.trickRoom,
        trick_room_turns:       0,
        tailwind_your_side:     allySide.tailwind,
        tailwind_your_turns:    0,
        tailwind_opponent_side: oppSide.tailwind,
        tailwind_opponent_turns: 0,
        screens_your_side:     { reflect: allySide.reflect, light_screen: allySide.lightScreen, aurora_veil: false },
        screens_opponent_side: { reflect: oppSide.reflect,  light_screen: oppSide.lightScreen,  aurora_veil: false },
      },
    };
  }, [allies, opponents, monStates, field, allySide, oppSide]);

  return (
    <div className="app">
      <div className="main-col">
        <div className="topbar">
          <div className="brand">
            <div className="brand-mark" />
            <div className="brand-text">
              <div className="brand-name">Champions Advisor</div>
              <div className="brand-tag">VGC DOUBLES · COACHING TOOL</div>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="format-pill"><span className="dot" />CHAMPIONS · L50</span>
            <button className="icon-btn" title="Reset board" onClick={resetBoard}>↻</button>
          </div>
        </div>

        <div className="battlefield">
          <div className="bf-ally-team">
            <TeamPreview side="ally" label="ALLY TEAM" roster={INITIAL_ALLY_TEAM} onField={allies.map(a => a.name)} />
          </div>
          <div className="bf-opp-team">
            <TeamPreview side="opponent" label="OPP TEAM" roster={INITIAL_OPP_TEAM} onField={opponents.map(o => o.name)} />
          </div>

          <div className="bf-ally-side">
            <SideStateBar side="ally" label="ALLY SIDE" state={allySide} onUpdate={p => setAllySide(prev => ({ ...prev, ...p }))} />
          </div>
          <div className="bf-opp-side">
            <SideStateBar side="opponent" label="OPP SIDE" state={oppSide} onUpdate={p => setOppSide(prev => ({ ...prev, ...p }))} />
          </div>

          <div className="bf-ally-slot1">
            <PokemonCard
              mon={allies[0]} side="ally" slot={1}
              state={monStates[allies[0].id]}
              onUpdate={p => updateMon(allies[0].id, p)}
              selectedMoveIdx={activeAttacker === allies[0].id ? selectedMove : null}
              onSelectMove={i => { setActiveAttacker(allies[0].id); setSelectedMove(i); }}
              isActive={activeAttacker === allies[0].id}
              onSetActive={() => setActiveAttacker(allies[0].id)}
            />
          </div>
          <div className="bf-opp-slot1">
            <PokemonCard
              mon={opponents[0]} side="opponent" slot={1}
              state={monStates[opponents[0].id]}
              onUpdate={p => updateMon(opponents[0].id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={false} onSetActive={() => {}}
            />
          </div>

          <div className="bf-field">
            <FieldBar field={field} onUpdate={p => setField(prev => ({ ...prev, ...p }))} />
          </div>

          <div className="bf-ally-slot2">
            <PokemonCard
              mon={allies[1]} side="ally" slot={2}
              state={monStates[allies[1].id]}
              onUpdate={p => updateMon(allies[1].id, p)}
              selectedMoveIdx={activeAttacker === allies[1].id ? selectedMove : null}
              onSelectMove={i => { setActiveAttacker(allies[1].id); setSelectedMove(i); }}
              isActive={activeAttacker === allies[1].id}
              onSetActive={() => setActiveAttacker(allies[1].id)}
            />
          </div>
          <div className="bf-opp-slot2">
            <PokemonCard
              mon={opponents[1]} side="opponent" slot={2}
              state={monStates[opponents[1].id]}
              onUpdate={p => updateMon(opponents[1].id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={false} onSetActive={() => {}}
            />
          </div>
        </div>
      </div>

      <div className="side-col">
        <AnalysisPanel buildPayload={buildPayload} allies={allies} field={field} />
      </div>
    </div>
  );
}
