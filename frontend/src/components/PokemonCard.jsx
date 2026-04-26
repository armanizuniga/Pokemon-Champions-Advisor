import { useState, useEffect, useRef } from 'react';
import TypeBadge from './TypeBadge';
import { TYPE_COLORS } from '../data/typeColors';

const STATUS_OPTS = [
  { id: 'none', label: '—' }, { id: 'brn', label: 'BRN' }, { id: 'par', label: 'PAR' },
  { id: 'psn',  label: 'PSN' }, { id: 'tox', label: 'TOX' }, { id: 'slp', label: 'SLP' },
  { id: 'frz',  label: 'FRZ' },
];

const NATURES = [
  'Hardy','Lonely','Brave','Adamant','Naughty','Bold','Docile','Relaxed','Impish','Lax',
  'Timid','Hasty','Serious','Jolly','Naive','Modest','Mild','Quiet','Bashful','Rash',
  'Calm','Gentle','Sassy','Careful','Quirky',
];

const STAT_KEYS   = ['hp','atk','def','spa','spd','spe'];
const STAT_LABELS = { hp:'HP', atk:'ATK', def:'DEF', spa:'SPA', spd:'SPD', spe:'SPE' };
const VOLATILES   = ['protect','taunt','encore','substitute','leech-seed','confusion'];

const NATURE_MODS = {
  Lonely:  { atk:1.1, def:0.9 }, Brave:   { atk:1.1, spe:0.9 },
  Adamant: { atk:1.1, spa:0.9 }, Naughty: { atk:1.1, spd:0.9 },
  Bold:    { def:1.1, atk:0.9 }, Relaxed: { def:1.1, spe:0.9 },
  Impish:  { def:1.1, spa:0.9 }, Lax:     { def:1.1, spd:0.9 },
  Timid:   { spe:1.1, atk:0.9 }, Hasty:   { spe:1.1, def:0.9 },
  Jolly:   { spe:1.1, spa:0.9 }, Naive:   { spe:1.1, spd:0.9 },
  Modest:  { spa:1.1, atk:0.9 }, Mild:    { spa:1.1, def:0.9 },
  Quiet:   { spa:1.1, spe:0.9 }, Rash:    { spa:1.1, spd:0.9 },
  Calm:    { spd:1.1, atk:0.9 }, Gentle:  { spd:1.1, def:0.9 },
  Sassy:   { spd:1.1, spe:0.9 }, Careful: { spd:1.1, spa:0.9 },
};

// Champions formula: HP = base + sp + 75, other = floor(n * (base + sp + 20))
function computeStat(key, base, sp, mult = 1.0) {
  if (key === 'hp') return base + sp + 75;
  return Math.floor(mult * (base + sp + 20));
}

// ── Searchable dropdown (items) ───────────────────────────────────────────────
function SearchableSelect({ value, options, onChange, placeholder = '—' }) {
  const [open,   setOpen]   = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setSearch(''); }
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [open]);

  const getLabel = o => typeof o === 'string' ? o : o.name;
  const filtered = options.filter(o => getLabel(o).toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="search-sel" ref={ref}>
      <button className="search-sel-btn" onClick={() => { setOpen(o => !o); setSearch(''); }}>
        <span className="search-sel-val">{value || placeholder}</span>
        <span className="search-sel-arrow">▾</span>
      </button>
      {open && (
        <div className="search-sel-drop">
          <input
            autoFocus
            className="slot-search"
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Escape') { setOpen(false); setSearch(''); }
              if (e.key === 'Enter' && filtered.length > 0) {
                onChange(getLabel(filtered[0])); setOpen(false); setSearch('');
              }
            }}
          />
          <div className="slot-list">
            <button className="slot-option dim-opt" onClick={() => { onChange(null); setOpen(false); setSearch(''); }}>
              — none
            </button>
            {filtered.map(o => {
              const name = getLabel(o);
              return (
                <button key={name} className={`slot-option ${value === name ? 'selected-opt' : ''}`}
                  onClick={() => { onChange(name); setOpen(false); setSearch(''); }}>
                  {name}
                </button>
              );
            })}
          </div>
          {filtered.length === 0 && <div className="slot-no-results">No results</div>}
        </div>
      )}
    </div>
  );
}

// ── Move picker dropdown ───────────────────────────────────────────────────────
function MovePicker({ moveIndex, selectedMove, availableMoves, onSelect }) {
  const [open,   setOpen]   = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setSearch(''); }
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [open]);

  const filtered = availableMoves.filter(m =>
    m.name.toLowerCase().includes(search.toLowerCase())
  );

  const current = selectedMove;
  const color   = TYPE_COLORS[current?.type] || '#888';
  const cat     = current?.category === 'Physical' ? 'PHY'
                : current?.category === 'Special'  ? 'SPE'
                : current?.category === 'Status'   ? 'STA' : null;

  return (
    <div className="move-picker-wrap" ref={ref}>
      <div className="move-picker-row">
        <button
          className={`move-pill ${current ? 'filled' : 'empty'}`}
          style={current ? { '--type-color': color } : {}}
          onClick={() => { setOpen(o => !o); setSearch(''); }}
        >
          {current ? (
            <>
              <span className="move-pill-dot" style={{ background: color }} />
              <span className="move-pill-name">{current.name}</span>
              {cat && <span className="move-pill-cat">{cat}</span>}
              {current.power > 0 && <span className="move-pill-power">{current.power}</span>}
              {current.type && <TypeBadge type={current.type} small />}
            </>
          ) : (
            <span className="move-pill-empty">+ Move {moveIndex + 1}</span>
          )}
        </button>
        {current && (
          <label className="crit-label" title="Critical hit">
            <input
              type="checkbox"
              checked={current.crit || false}
              onChange={e => onSelect({ ...current, crit: e.target.checked })}
            />
            <span>Crit</span>
          </label>
        )}
      </div>

      {open && (
        <div className="move-dropdown">
          <input
            autoFocus
            className="slot-search"
            placeholder="Search moves…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Escape') { setOpen(false); setSearch(''); }
              if (e.key === 'Enter' && filtered.length > 0) {
                onSelect(filtered[0]); setOpen(false); setSearch('');
              }
            }}
          />
          <div className="slot-list">
            {filtered.map(m => {
              const c = TYPE_COLORS[m.type] || '#888';
              const mc = m.category === 'Physical' ? 'PHY' : m.category === 'Special' ? 'SPE' : m.category === 'Status' ? 'STA' : '—';
              return (
                <button key={m.name} className="move-option" onClick={() => { onSelect(m); setOpen(false); setSearch(''); }}>
                  <span className="move-opt-dot" style={{ background: c }} />
                  <span className="move-opt-name">{m.name}</span>
                  <span className="move-opt-meta">
                    {m.type && <TypeBadge type={m.type} small />}
                    <span className="move-opt-cat">{mc}</span>
                    {m.power > 0 && <span className="move-opt-power">{m.power}</span>}
                  </span>
                </button>
              );
            })}
            {filtered.length === 0 && <div className="slot-no-results">No results</div>}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────────
export default function PokemonCard({
  mon, side, slot, state, onUpdate,
  selectedMoveIdx, onSelectMove,
  isActive, onSetActive,
  itemsList,
}) {
  const [expanded, setExpanded] = useState(false);
  if (!mon || !state) return <div className="poke-card empty">— empty —</div>;

  const SP_MAX     = 32;
  const SP_BANK    = 64;

  const base      = mon.baseStats || {};
  const evs       = state.evs || { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
  const totalEvs  = Object.values(evs).reduce((a, b) => a + b, 0);
  const remaining = SP_BANK - totalEvs;

  function setEv(key, val) {
    const clamped = Math.min(SP_MAX, Math.max(0, val));
    const headroom = remaining + evs[key];
    const next = { ...evs, [key]: Math.min(clamped, headroom) };
    onUpdate({ evs: next });
  }

  function selectMove(i, moveObj) {
    const moves = [...(state.selectedMoves || [null, null, null, null])];
    moves[i] = moveObj;
    onUpdate({ selectedMoves: moves });
  }

  const selectedMoves = state.selectedMoves || [null, null, null, null];

  return (
    <div className={`poke-card ${side} ${isActive ? 'active' : ''}`}>

      {/* Header */}
      <div className="poke-header">
        <div className="poke-header-left">
          <button className={`active-toggle ${isActive ? 'on' : ''}`} onClick={onSetActive} title="Set as primary attacker">
            <span className="active-dot" />
          </button>
          <div>
            <div className="poke-name-row">
              <span className="poke-name">{mon.name}</span>
              <span className="poke-level mono">L{mon.level}</span>
            </div>
          </div>
        </div>
        <div className="poke-header-right">
          {(mon.types || []).map(t => <TypeBadge key={t} type={t} />)}
        </div>
      </div>

      {/* HP slider */}
      <div className="hp-slider-row">
        <input
          type="range" min="0" max={mon.stats.hp} value={state.hp}
          className="hp-slider"
          onChange={e => onUpdate({ hp: Number(e.target.value) })}
        />
        <span className="hp-readout mono">
          {state.hp}<span className="dim-text">/{mon.stats.hp}</span>
          <span className="hp-pct"> {Math.round(state.hp / mon.stats.hp * 100)}%</span>
        </span>
      </div>

      {/* Quick row: ability / item / nature / status */}
      <div className="poke-quick">
        <div className="quick-cell">
          <span className="quick-label">ABILITY</span>
          <select className="quick-select" value={state.ability || ''} onChange={e => onUpdate({ ability: e.target.value || null })}>
            <option value="">—</option>
            {(mon.abilities || []).map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div className="quick-cell">
          <span className="quick-label">ITEM</span>
          <SearchableSelect
            value={state.item}
            options={itemsList || []}
            onChange={v => onUpdate({ item: v })}
          />
        </div>
        <div className="quick-cell">
          <span className="quick-label">NATURE</span>
          <select className="quick-select" value={state.nature || ''} onChange={e => onUpdate({ nature: e.target.value || null })}>
            <option value="">—</option>
            {NATURES.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="quick-cell">
          <span className="quick-label">STATUS</span>
          <select className="status-select" value={state.status} onChange={e => onUpdate({ status: e.target.value })}>
            {STATUS_OPTS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
      </div>

      {/* Stats: vertical with EV sliders + nature */}
      <div className="stats-block">
        <div className="ev-bank-row">
          <span className="ev-bank-label">SP</span>
          <span className="ev-bank-used mono">{totalEvs}</span>
          <span className="ev-bank-sep">/{SP_BANK}</span>
          <span className={`ev-bank-left mono ${remaining === 0 ? 'ev-full' : ''}`}>{remaining} left</span>
        </div>
        {(() => {
          const natureMods = NATURE_MODS[state.nature] || {};
          return STAT_KEYS.map(k => {
            const baseVal   = base[k] || 0;
            const ev        = evs[k] || 0;
            const mult      = natureMods[k] || 1.0;
            const computed  = computeStat(k, baseVal, ev, mult);
            const barPct    = Math.round((computed / 200) * 100);
            const barColor  = side === 'ally' ? 'var(--ally)' : 'var(--enemy)';
            const natClass  = mult > 1 ? 'nat-up' : mult < 1 ? 'nat-down' : '';
            const sliderMax = Math.min(SP_MAX, ev + remaining);
            return (
              <div key={k} className="stat-row">
                <span className={`stat-row-label ${natClass}`}>{STAT_LABELS[k]}{mult > 1 ? ' ↑' : mult < 1 ? ' ↓' : ''}</span>
                <span className="stat-row-base mono">{baseVal}</span>
                <div className="stat-bar-wrap">
                  <div className="stat-bar-fill" style={{ width: `${Math.min(100, barPct)}%`, background: barColor }} />
                </div>
                <span className={`stat-row-val mono ${natClass}`}>{computed}</span>
                <input
                  type="range" min="0" max={sliderMax} step="4" value={ev}
                  className="ev-slider"
                  onChange={e => setEv(k, Number(e.target.value))}
                />
                <input
                  type="number" min="0" max={sliderMax} step="4" value={ev}
                  className="ev-num-input mono"
                  onChange={e => setEv(k, Number(e.target.value))}
                />
              </div>
            );
          });
        })()}
      </div>

      {/* Moves */}
      <div className="moves-list">
        {[0, 1, 2, 3].map(i => (
          <MovePicker
            key={i}
            moveIndex={i}
            selectedMove={selectedMoves[i]}
            availableMoves={mon.availableMoves || []}
            onSelect={mv => selectMove(i, mv)}
          />
        ))}
      </div>

      {/* Expand: stages + conditions */}
      <button className="expand-toggle" onClick={() => setExpanded(e => !e)}>
        {expanded ? '▾ Hide stages & conditions' : '▸ Stages & conditions'}
      </button>

      {expanded && (
        <div className="advanced-controls">
          <div>
            <div className="ctrl-section-title">STAT STAGES</div>
            <div className="stages-grid">
              {['atk','def','spa','spd','spe'].map(s => (
                <div key={s} className="stage-ctrl">
                  <span className="stage-label">{STAT_LABELS[s]}</span>
                  <button className="stage-btn" onClick={() => {
                    const v = (state.stages[s] || 0);
                    onUpdate({ stages: { ...state.stages, [s]: Math.max(-6, v - 1) } });
                  }}>−</button>
                  <span className={`stage-val ${(state.stages[s]||0) > 0 ? 'pos' : (state.stages[s]||0) < 0 ? 'neg' : ''}`}>
                    {(state.stages[s]||0) > 0 ? `+${state.stages[s]}` : state.stages[s]||0}
                  </span>
                  <button className="stage-btn" onClick={() => {
                    const v = (state.stages[s] || 0);
                    onUpdate({ stages: { ...state.stages, [s]: Math.min(6, v + 1) } });
                  }}>+</button>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="ctrl-section-title">CONDITIONS</div>
            <div className="volatiles-grid">
              {VOLATILES.map(v => (
                <label key={v} className="volatile-chip">
                  <input
                    type="checkbox"
                    checked={(state.volatiles || []).includes(v)}
                    onChange={e => {
                      const next = e.target.checked
                        ? [...(state.volatiles || []), v]
                        : (state.volatiles || []).filter(x => x !== v);
                      onUpdate({ volatiles: next });
                    }}
                  />
                  <span>{v}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
