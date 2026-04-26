import { useState, useCallback, useEffect } from 'react';
import FieldBar, { SideStateBar } from './components/FieldBar';
import PokemonCard from './components/PokemonCard';
import AnalysisPanel from './components/AnalysisPanel';
import PokemonSlotPicker from './components/PokemonSlotPicker';

// ── Helpers ───────────────────────────────────────────────────────────────────

const makeEmpty6 = () => [null, null, null, null, null, null];

function makeMonState(mon) {
  return {
    hp:            mon.stats.hp,
    status:        'none',
    stages:        { atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    volatiles:     [],
    ability:       mon.ability  || null,
    item:          mon.item     || null,
    nature:        mon.nature   || null,
    evs:           { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    selectedMoves: [null, null, null, null],
  };
}

function buildMonFromApiData(slug, name, apiData, side, loadMoves) {
  const b = apiData.base_stats || {};
  // Champions formula at 0 SP: HP = base + 75, other = base + 20
  const stats = {
    hp:  (b.hp  || 50) + 75,
    atk: (b.atk || 50) + 20,
    def: (b.def || 50) + 20,
    spa: (b.spa || 50) + 20,
    spd: (b.spd || 50) + 20,
    spe: (b.spe || 50) + 20,
  };
  const moveDetails = apiData.move_details || [];
  const initialMoves = loadMoves
    ? moveDetails.slice(0, 4).map(m => ({ name: m.name, type: m.type, category: m.category, power: m.power || 0 }))
    : [null, null, null, null];
  return {
    id:             `${side}-${slug}`,
    name,
    types:          [],
    ability:        apiData.abilities?.[0] ?? null,
    abilities:      apiData.abilities || [],
    item:           null,
    nature:         null,
    level:          50,
    baseStats:      b,
    evs:            { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 },
    stats,
    availableMoves: moveDetails,
    moves:          [],
  };
}

// ── Slot role cycling ──────────────────────────────────────────────────────────
// Cycling order: none → lead (if < 2 leads) → back (if < 2 backs) → none
function nextRole(currentRole, slots) {
  const leadCount = slots.filter(s => s?.role === 'lead').length;
  const backCount = slots.filter(s => s?.role === 'back').length;
  if (currentRole === 'none') {
    if (leadCount < 2) return 'lead';
    if (backCount < 2) return 'back';
    return 'none';
  }
  if (currentRole === 'lead') {
    if (backCount < 2) return 'back';
    return 'none';
  }
  return 'none'; // back → none
}

export default function App() {
  const [pokemonList, setPokemonList] = useState([]);
  const [itemsList,   setItemsList]   = useState([]);
  const [allySlots,   setAllySlots]   = useState(makeEmpty6);
  const [oppSlots,    setOppSlots]    = useState(makeEmpty6);
  const [allyMons,    setAllyMons]    = useState({});
  const [oppMons,     setOppMons]     = useState({});
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

  // ── Fetch static lists once ─────────────────────────────────────────────────
  useEffect(() => {
    fetch('/api/pokemon').then(r => r.ok ? r.json() : []).then(setPokemonList).catch(() => {});
    fetch('/api/items').then(r => r.ok ? r.json() : []).then(setItemsList).catch(() => {});
  }, []);

  // ── Mon state helpers ───────────────────────────────────────────────────────
  const updateMon = useCallback((id, patch) => {
    setMonStates(prev => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }, []);

  // ── Slot selection ──────────────────────────────────────────────────────────
  async function handleSlotSelect(index, slug, name, side, setSlots, setMons, loadMoves) {
    // Always fetch data for every slot — any slot can become a lead via role cycling
    try {
      const res = await fetch(`/api/pokemon/${slug}`);
      if (!res.ok) return;
      const data = await res.json();
      const mon  = buildMonFromApiData(slug, name, data, side, loadMoves);
      const initialState = makeMonState(mon);
      if (loadMoves && data.move_details) {
        initialState.selectedMoves = data.move_details.slice(0, 4).map(m => ({
          name: m.name, type: m.type, category: m.category, power: m.power || 0,
        }));
      }
      setSlots(prev => {
        const n = [...prev];
        n[index] = { slug, name, role: 'none' };
        return n;
      });
      setMons(prev      => ({ ...prev, [mon.id]: mon }));
      setMonStates(prev => ({ ...prev, [mon.id]: initialState }));
    } catch {}
  }

  function handleSlotClear(index, side, setSlots, setMons) {
    const sidePrefix = side;
    setSlots(prev => {
      const n = [...prev];
      const old = n[index];
      if (old) {
        const monId = `${sidePrefix}-${old.slug}`;
        setMons(m => { const c = { ...m }; delete c[monId]; return c; });
        setMonStates(s => { const c = { ...s }; delete c[monId]; return c; });
      }
      n[index] = null;
      return n;
    });
  }

  function handleCycleRole(index, setSlots) {
    setSlots(prev => {
      const n   = [...prev];
      const slot = n[index];
      if (!slot) return n;
      n[index] = { ...slot, role: nextRole(slot.role, prev) };
      return n;
    });
  }

  function resetBoard() {
    setAllySlots(makeEmpty6());
    setOppSlots(makeEmpty6());
    setAllyMons({});
    setOppMons({});
    setMonStates({});
    setField({ weather: 'none', terrain: 'none', trickRoom: false, gravity: false, turn: 1 });
    setAllySide({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });
    setOppSide({ reflect: false, lightScreen: false, tailwind: false, stealthRock: false });
    setActiveAttacker(null);
  }

  // ── Payload builder ─────────────────────────────────────────────────────────
  const buildPayload = useCallback(() => {
    const monToPayload = (mon, state) => ({
      species:    mon.name,
      hp_percent: state.hp / mon.stats.hp,
      item:       state.item   || null,
      ability:    state.ability || null,
      status:     state.status !== 'none' ? state.status : null,
      boosts:     state.stages,
      moves:      (state.selectedMoves || []).filter(Boolean).map(m => m.name),
    });

    const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

    const allyLeads = allySlots.filter(s => s?.role === 'lead').map(s => allyMons[`ally-${s.slug}`]).filter(Boolean);
    const allyBacks = allySlots.filter(s => s?.role === 'back');
    const oppLeads  = oppSlots.filter(s => s?.role === 'lead').map(s => oppMons[`opp-${s.slug}`]).filter(Boolean);
    const oppBacks  = oppSlots.filter(s => s?.role === 'back');

    return {
      turn:            field.turn,
      your_active:     allyLeads.map(m => monToPayload(m, monStates[m.id])),
      opponent_active: oppLeads.map(m => monToPayload(m, monStates[m.id])),
      your_back:       allyBacks.map(s => ({ species: s.name, hp_percent: 1.0 })),
      opponent_back:   oppBacks.map(s => ({ species: s.name, hp_percent: 1.0 })),
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
  }, [allySlots, oppSlots, allyMons, oppMons, monStates, field, allySide, oppSide]);

  // ── Derive active mons from lead slots ──────────────────────────────────────
  const allyLeadSlots = allySlots.filter(s => s?.role === 'lead');
  const oppLeadSlots  = oppSlots.filter(s => s?.role === 'lead');
  const ally0  = allyLeadSlots[0] ? allyMons[`ally-${allyLeadSlots[0].slug}`] ?? null : null;
  const ally1  = allyLeadSlots[1] ? allyMons[`ally-${allyLeadSlots[1].slug}`] ?? null : null;
  const opp0   = oppLeadSlots[0]  ? oppMons[`opp-${oppLeadSlots[0].slug}`]    ?? null : null;
  const opp1   = oppLeadSlots[1]  ? oppMons[`opp-${oppLeadSlots[1].slug}`]    ?? null : null;
  const stateA0 = ally0 ? (monStates[ally0.id] ?? makeMonState(ally0)) : null;
  const stateA1 = ally1 ? (monStates[ally1.id] ?? makeMonState(ally1)) : null;
  const stateO0 = opp0  ? (monStates[opp0.id]  ?? makeMonState(opp0))  : null;
  const stateO1 = opp1  ? (monStates[opp1.id]  ?? makeMonState(opp1))  : null;

  const visibleAllies    = [ally0, ally1].filter(Boolean);
  const visibleOpponents = [opp0,  opp1].filter(Boolean);

  return (
    <div className="app">
      <div className="main-col">

        {/* Top bar */}

        <div className="topbar">
          <div className="topbar-brand-center">
            <div className="brand-name">Pokémon Champions Advisor</div>
            <div className="brand-tag">VGC DOUBLES · COACHING TOOL</div>
          </div>
          <div className="topbar-actions">
            <span className="format-pill"><span className="dot" />CHAMPIONS · L50</span>
            <button className="icon-btn" title="Reset board" onClick={resetBoard}>↻</button>
          </div>
        </div>

        <div className="battlefield">

          {/* Team pickers — row 1 */}
          <div className="bf-ally-team">
            <PokemonSlotPicker
              slots={allySlots}
              onSelect={(i, slug, name) => handleSlotSelect(i, slug, name, 'ally', setAllySlots, setAllyMons, true)}
              onClear={i => handleSlotClear(i, 'ally', setAllySlots, setAllyMons)}
              onCycleRole={i => handleCycleRole(i, setAllySlots)}
              pokemonList={pokemonList}
              label="YOUR TEAM"
              side="ally"
            />
          </div>
          <div className="bf-opp-team">
            <PokemonSlotPicker
              slots={oppSlots}
              onSelect={(i, slug, name) => handleSlotSelect(i, slug, name, 'opp', setOppSlots, setOppMons, false)}
              onClear={i => handleSlotClear(i, 'opp', setOppSlots, setOppMons)}
              onCycleRole={i => handleCycleRole(i, setOppSlots)}
              pokemonList={pokemonList}
              label="OPPONENT'S TEAM"
              side="opponent"
            />
          </div>

          {/* Side state bars — row 2 */}
          <div className="bf-ally-side">
            <SideStateBar side="ally" state={allySide} onUpdate={p => setAllySide(prev => ({ ...prev, ...p }))} />
          </div>
          <div className="bf-opp-side">
            <SideStateBar side="opponent" state={oppSide} onUpdate={p => setOppSide(prev => ({ ...prev, ...p }))} />
          </div>

          {/* Field bar — spans all rows */}
          <div className="bf-field">
            <FieldBar field={field} onUpdate={p => setField(prev => ({ ...prev, ...p }))} />
          </div>

          {/* Pokémon cards — rows 3-4 */}
          <div className="bf-ally-slot1">
            <PokemonCard
              mon={ally0} side="ally" slot={1}
              state={stateA0}
              onUpdate={p => ally0 && updateMon(ally0.id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={activeAttacker === ally0?.id}
              onSetActive={() => setActiveAttacker(ally0?.id)}
              itemsList={itemsList}
            />
          </div>
          <div className="bf-opp-slot1">
            <PokemonCard
              mon={opp0} side="opponent" slot={1}
              state={stateO0}
              onUpdate={p => opp0 && updateMon(opp0.id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={false} onSetActive={() => {}}
              itemsList={itemsList}
            />
          </div>

          <div className="bf-ally-slot2">
            <PokemonCard
              mon={ally1} side="ally" slot={2}
              state={stateA1}
              onUpdate={p => ally1 && updateMon(ally1.id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={activeAttacker === ally1?.id}
              onSetActive={() => setActiveAttacker(ally1?.id)}
              itemsList={itemsList}
            />
          </div>
          <div className="bf-opp-slot2">
            <PokemonCard
              mon={opp1} side="opponent" slot={2}
              state={stateO1}
              onUpdate={p => opp1 && updateMon(opp1.id, p)}
              selectedMoveIdx={null} onSelectMove={() => {}}
              isActive={false} onSetActive={() => {}}
              itemsList={itemsList}
            />
          </div>

        </div>
      </div>

      <div className="bottom-panel">
        <AnalysisPanel buildPayload={buildPayload} allies={visibleAllies} opponents={visibleOpponents} field={field} />
      </div>
    </div>
  );
}
