import { useState } from 'react';
import TypeBadge from './TypeBadge';
import MoveRow from './MoveRow';

const STATUS_OPTS = [
  { id: 'none', label: '—' }, { id: 'brn', label: 'BRN' }, { id: 'par', label: 'PAR' },
  { id: 'psn',  label: 'PSN' }, { id: 'tox', label: 'TOX' }, { id: 'slp', label: 'SLP' },
  { id: 'frz',  label: 'FRZ' },
];

const STAT_KEYS   = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];
const STAT_LABELS = { hp: 'HP', atk: 'ATK', def: 'DEF', spa: 'SPA', spd: 'SPD', spe: 'SPE' };
const MAX_STATS   = { hp: 255, atk: 210, def: 230, spa: 210, spd: 230, spe: 200 };
const VOLATILES   = ['protect', 'taunt', 'encore', 'substitute', 'leech-seed', 'confusion'];

function HPBar({ current, max }) {
  const pct = Math.max(0, Math.min(100, (current / max) * 100));
  const color = pct > 50 ? 'oklch(0.72 0.16 145)' : pct > 20 ? 'oklch(0.78 0.16 80)' : 'oklch(0.65 0.20 25)';
  return (
    <div className="hp-bar-wrap">
      <div className="hp-bar-track">
        <div className="hp-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="hp-bar-text">
        <span className="mono">{current}</span>
        <span className="hp-divider">/</span>
        <span className="mono">{max}</span>
        <span className="hp-pct mono">{pct.toFixed(0)}%</span>
      </div>
    </div>
  );
}

function StatStageControl({ stat, value, onChange }) {
  return (
    <div className="stage-ctrl">
      <span className="stage-label">{STAT_LABELS[stat]}</span>
      <button className="stage-btn" onClick={() => onChange(Math.max(-6, value - 1))}>−</button>
      <span className={`stage-val ${value > 0 ? 'pos' : value < 0 ? 'neg' : ''}`}>
        {value > 0 ? `+${value}` : value}
      </span>
      <button className="stage-btn" onClick={() => onChange(Math.min(6, value + 1))}>+</button>
    </div>
  );
}

export default function PokemonCard({
  mon, side, slot, state, onUpdate,
  selectedMoveIdx, onSelectMove,
  isActive, onSetActive,
}) {
  const [expanded, setExpanded] = useState(false);
  if (!mon) return <div className="poke-card empty">Empty Slot</div>;

  const sideLabel = side === 'ally' ? 'ALLY' : 'OPPONENT';

  return (
    <div className={`poke-card ${side} ${isActive ? 'active' : ''}`}>
      <div className="poke-header">
        <div className="poke-header-left">
          <button className={`active-toggle ${isActive ? 'on' : ''}`} onClick={onSetActive} title="Set as primary attacker">
            <span className="active-dot" />
          </button>
          <div>
            <div className="poke-side-label">{sideLabel} · SLOT {slot}</div>
            <div className="poke-name-row">
              <span className="poke-name">{mon.name}</span>
              <span className="poke-level mono">L{mon.level}</span>
            </div>
          </div>
        </div>
        <div className="poke-header-right">
          {mon.types.map(t => <TypeBadge key={t} type={t} />)}
        </div>
      </div>

      <HPBar current={state.hp} max={mon.stats.hp} />

      <div className="poke-quick">
        <div className="quick-cell">
          <span className="quick-label">ABILITY</span>
          <span className="quick-val">{mon.ability || '?'}</span>
        </div>
        <div className="quick-cell">
          <span className="quick-label">ITEM</span>
          <span className="quick-val">{mon.item || '?'}</span>
        </div>
        <div className="quick-cell">
          <span className="quick-label">NATURE</span>
          <span className="quick-val">{mon.nature || '—'}</span>
        </div>
        <div className="quick-cell">
          <span className="quick-label">STATUS</span>
          <select
            className="status-select"
            value={state.status}
            onChange={e => onUpdate({ status: e.target.value })}
          >
            {STATUS_OPTS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
      </div>

      <div className="stats-grid">
        {STAT_KEYS.map(k => {
          const barPct = Math.round((mon.stats[k] / (MAX_STATS[k] || 200)) * 100);
          const barColor = side === 'ally' ? 'var(--ally)' : 'var(--enemy)';
          return (
            <div key={k} className="stat-cell" style={{ '--bar': `${barPct}%`, '--bar-color': barColor }}>
              <div className="stat-label">{STAT_LABELS[k]}</div>
              <div className="stat-val mono">{mon.stats[k]}</div>
              <div className="stat-meta mono">{mon.evs[k]}</div>
            </div>
          );
        })}
      </div>

      {mon.moves.length > 0 && (
        <div className="moves-list">
          {mon.moves.map((m, i) => (
            <MoveRow
              key={i}
              move={m}
              isSelected={selectedMoveIdx === i}
              onClick={() => onSelectMove(i)}
              dim={!isActive}
            />
          ))}
        </div>
      )}

      {mon.moves.length === 0 && (
        <div style={{ fontSize: '10px', color: 'var(--text-faint)', fontStyle: 'italic', padding: '4px 0' }}>
          Moves not yet revealed
        </div>
      )}

      <button className="expand-toggle" onClick={() => setExpanded(e => !e)}>
        {expanded ? '▾ Hide controls' : '▸ Show stages & conditions'}
      </button>

      {expanded && (
        <div className="advanced-controls">
          <div>
            <div className="ctrl-section-title">HP</div>
            <input
              type="range" min="0" max={mon.stats.hp} value={state.hp}
              className="hp-slider"
              onChange={e => onUpdate({ hp: Number(e.target.value) })}
            />
          </div>
          <div>
            <div className="ctrl-section-title">STAT STAGES</div>
            <div className="stages-grid">
              {['atk', 'def', 'spa', 'spd', 'spe'].map(s => (
                <StatStageControl
                  key={s} stat={s} value={state.stages[s]}
                  onChange={v => onUpdate({ stages: { ...state.stages, [s]: v } })}
                />
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
                    checked={state.volatiles.includes(v)}
                    onChange={e => {
                      const next = e.target.checked
                        ? [...state.volatiles, v]
                        : state.volatiles.filter(x => x !== v);
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
