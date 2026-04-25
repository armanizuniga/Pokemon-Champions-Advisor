import { useState, useCallback, useEffect } from 'react';
import FieldBar, { SideStateBar } from './components/FieldBar';
import PokemonCard from './components/PokemonCard';
import AnalysisPanel from './components/AnalysisPanel';
import PokemonSlotPicker from './components/PokemonSlotPicker';
import { makeMonState } from './data/initialState';

const makeEmpty6 = () => [null, null, null, null, null, null];

function buildMonFromApiData(slug, name, apiData, side, loadMoves) {
  const b = apiData.base_stats || {};
  const stats = {
    hp:  (b.hp  || 50) + 60,
    atk: (b.atk || 50) + 5,
    def: (b.def || 50) + 5,
    spa: (b.spa || 50) + 5,
    spd: (b.spd || 50) + 5,
    spe: (b.spe || 50) + 5,
  };
  return {
    id:        `${side}-${slug}`,
    name,
    types:     [],
    ability:   apiData.abilities?.[0] ?? null,
    item:      null,
    nature:    null,
    level:     50,
    baseStats: b,
    evs:       { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    stats,
    moves:     loadMoves ? (apiData.moves || []).slice(0, 4).map(m => ({ name: m })) : [],
  };
}

export default function App() {
  const [pokemonList, setPokemonList] = useState([]);
  const [allySlots,   setAllySlots]   = useState(makeEmpty6);
  const [oppSlots,    setOppSlots]    = useState(makeEmpty6);
  const [allies,      setAllies]      = useState([null, null]);
  const [opponents,   setOpponents]   = useState([null, null]);
  const [monStates,   setMonStates]   = useState({});

  const [field, setField] = useState({
    weather: 'none', terrain: 'none', trickRoom: false, gravity: false, turn: 1,
  });

  const [allySide, setAllySide] = useState(
    { reflect: false, lightScreen: false, tailwind: false, stealthRock: false }
  );
  const [oppSide, setOppSide] = useState(
    { reflect: false, lightScreen: false, tailwind: false, stealthRock: false }
  );

  const [activeAttacker, setActiveAttacker] = useState(null);
  const [selectedMove,   setSelectedMove]   = useState(null);

  useEffect(() => {
    fetch('/api/pokemon')
      .then(r => r.ok ? r.json() : [])
      .then(list => setPokemonList(list))
      .catch(() => {});
  }, []);

  const updateMon = useCallback((id, patch) => {
    setMonStates(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }, []);

  async function handleSlotSelect(index, slug, name, side, setSlots, setActive, loadMoves) {
    if (index >= 2) {
      setSlots(prev => { const n = [...prev]; n[index] = { slug, name }; return n; });
      return;
    }
    try {
      const res = await fetch(`/api/pokemon/${slug}`);
      if (!res.ok) return;
      const data = await res.json();
      const mon  = buildMonFromApiData(slug, name, data, side, loadMoves);
      setSlots(prev    => { const n = [...prev]; n[index] = { slug, name }; return n; });
      setActive(prev   => { const n = [...prev]; n[index] = mon;            return n; });
      setMonStates(prev => ({ ...prev, [mon.id]: makeMonState(mon) }));
    } catch {}
  }

  function handleSlotClear(index, setSlots, setActive) {
    setSlots(prev => { const n = [...prev]; n[index] = null; return n; });
    if (index < 2) {
      setActive(prev => { const n = [...prev]; n[index] = null; return n; });
    }
  }

  function resetBoard() {
    setAllySlots(makeEmpty6());
    setOppSlots(makeEmpty6());
    setAllies([null, null]);
    setOpponents([null, null]);
    setMonStates({});
    setField({ weather: 'none', terrain: 'none', trickRoom: false, gravity: false, turn: 1 });
    setAllySide({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });
    setOppSide({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });
    setSelectedMove(null);
    setActiveAttacker(null);
  }

  const buildPayload = useCallback(() => {
    const monToPayload = (mon, state) => ({
      species:    mon.name,
      hp_percent: state.hp / mon.stats.hp,
      item:       mon.item || null,
      ability:    mon.ability || null,
      status:     state.status !== 'none' ? state.status : null,
      boosts:     state.stages,
      moves:      mon.moves.map(m => typeof m === 'string' ? m : m.name),
    });

    const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

    return {
      turn:            field.turn,
      your_active:     allies.filter(Boolean).map(m => monToPayload(m, monStates[m.id])),
      opponent_active: opponents.filter(Boolean).map(m => monToPayload(m, monStates[m.id])),
      your_back:       allySlots.slice(2).filter(Boolean).map(s => ({ species: s.name, hp_percent: 1.0 })),
      opponent_back:   oppSlots.slice(2).filter(Boolean).map(s => ({ species: s.name, hp_percent: 1.0 })),
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
  }, [allies, opponents, monStates, field, allySide, oppSide, allySlots, oppSlots]);

  const ally0  = allies[0];
  const ally1  = allies[1];
  const opp0   = opponents[0];
  const opp1   = opponents[1];
  const stateA0 = ally0 ? (monStates[ally0.id] ?? makeMonState(ally0)) : null;
  const stateA1 = ally1 ? (monStates[ally1.id] ?? makeMonState(ally1)) : null;
  const stateO0 = opp0  ? (monStates[opp0.id]  ?? makeMonState(opp0))  : null;
  const stateO1 = opp1  ? (monStates[opp1.id]  ?? makeMonState(opp1))  : null;

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
            <PokemonSlotPicker
              slots={allySlots}
              onSelect={(i, slug, name) => handleSlotSelect(i, slug, name, 'ally', setAllySlots, setAllies, true)}
              onClear={i => handleSlotClear(i, setAllySlots, setAllies)}
              pokemonList={pokemonList}
              label="ALLY TEAM"
              side="ally"
            />
          </div>
          <div className="bf-opp-team">
            <PokemonSlotPicker
              slots={oppSlots}
              onSelect={(i, slug, name) => handleSlotSelect(i, slug, name, 'opp', setOppSlots, setOpponents, false)}
              onClear={i => handleSlotClear(i, setOppSlots, setOpponents)}
              pokemonList={pokemonList}
              label="OPP TEAM"
              side="opponent"
            />
          </div>

          <div className="bf-ally-side">
            <SideStateBar side="ally" label="ALLY SIDE" state={allySide} onUpdate={p => setAllySide(prev => ({ ...prev, ...p }))} />
          </div>
          <div className="bf-opp-side">
            <SideStateBar side="opponent" label="OPP SIDE" state={oppSide} onUpdate={p => setOppSide(prev => ({ ...prev, ...p }))} />
          </div>

          <div className="bf-ally-slot1">
            <PokemonCard
              mon={ally0} side="ally" slot={1}
              state={stateA0}
              onUpdate={p => ally0 && updateMon(ally0.id, p)}
              selectedMoveIdx={activeAttacker === ally0?.id ? selectedMove : null}
              onSelectMove={i => { setActiveAttacker(ally0?.id); setSelectedMove(i); }}
              isActive={activeAttacker === ally0?.id}
              onSetActive={() => setActiveAttacker(ally0?.id)}
            />
          </div>
          <div className="bf-opp-slot1">
            <PokemonCard
              mon={opp0} side="opponent" slot={1}
              state={stateO0}
              onUpdate={p => opp0 && updateMon(opp0.id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={false} onSetActive={() => {}}
            />
          </div>

          <div className="bf-field">
            <FieldBar field={field} onUpdate={p => setField(prev => ({ ...prev, ...p }))} />
          </div>

          <div className="bf-ally-slot2">
            <PokemonCard
              mon={ally1} side="ally" slot={2}
              state={stateA1}
              onUpdate={p => ally1 && updateMon(ally1.id, p)}
              selectedMoveIdx={activeAttacker === ally1?.id ? selectedMove : null}
              onSelectMove={i => { setActiveAttacker(ally1?.id); setSelectedMove(i); }}
              isActive={activeAttacker === ally1?.id}
              onSetActive={() => setActiveAttacker(ally1?.id)}
            />
          </div>
          <div className="bf-opp-slot2">
            <PokemonCard
              mon={opp1} side="opponent" slot={2}
              state={stateO1}
              onUpdate={p => opp1 && updateMon(opp1.id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={false} onSetActive={() => {}}
            />
          </div>
        </div>
      </div>

      <div className="side-col">
        <AnalysisPanel buildPayload={buildPayload} allies={allies.filter(Boolean)} field={field} />
      </div>
    </div>
  );
}
