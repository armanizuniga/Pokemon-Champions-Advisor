// Pokemon card component — shows full state for one mon

const STATUS_OPTIONS = [
  { id: "none", label: "—", color: "#6b7280" },
  { id: "brn", label: "BRN", color: "#e08a4d" },
  { id: "par", label: "PAR", color: "#d4b73c" },
  { id: "psn", label: "PSN", color: "#a55cb0" },
  { id: "tox", label: "TOX", color: "#7d3a8a" },
  { id: "slp", label: "SLP", color: "#7080a0" },
  { id: "frz", label: "FRZ", color: "#8ec9d4" }
];

const STAT_KEYS = ["hp", "atk", "def", "spa", "spd", "spe"];
const STAT_LABELS = { hp: "HP", atk: "ATK", def: "DEF", spa: "SPA", spd: "SPD", spe: "SPE" };

function TypeBadge({ type, small }) {
  const color = window.TYPE_COLORS[type] || "#888";
  return (
    <span className="type-badge" style={{
      background: `${color}28`,
      color: color,
      border: `1px solid ${color}66`,
      fontSize: small ? "9px" : "10px",
      padding: small ? "1px 5px" : "2px 7px"
    }}>{type.toUpperCase()}</span>
  );
}

function HPBar({ current, max, side }) {
  const pct = Math.max(0, Math.min(100, (current / max) * 100));
  const color = pct > 50 ? "oklch(0.72 0.16 145)" : pct > 20 ? "oklch(0.78 0.16 80)" : "oklch(0.65 0.20 25)";
  return (
    <div className="hp-bar-wrap">
      <div className="hp-bar-track">
        <div className="hp-bar-fill" style={{ width: `${pct}%`, background: color }}></div>
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
      <span className={`stage-val ${value > 0 ? "pos" : value < 0 ? "neg" : ""}`}>
        {value > 0 ? `+${value}` : value}
      </span>
      <button className="stage-btn" onClick={() => onChange(Math.min(6, value + 1))}>+</button>
    </div>
  );
}

function MoveRow({ move, isSelected, onClick, damageInfo, dim }) {
  const color = window.TYPE_COLORS[move.type] || "#888";
  return (
    <button
      className={`move-row ${isSelected ? "selected" : ""} ${dim ? "dim" : ""}`}
      onClick={onClick}
      style={{ "--type-color": color }}
    >
      <div className="move-row-main">
        <span className="move-name">{move.name}</span>
        <TypeBadge type={move.type} small />
      </div>
      <div className="move-row-meta mono">
        <span className="move-cat" title={move.category}>
          {move.category === "Physical" ? "PHY" : move.category === "Special" ? "SPE" : "STA"}
        </span>
        <span>{move.power || "—"}<span className="dim-text">bp</span></span>
        <span>{move.acc}<span className="dim-text">%</span></span>
        <span>{move.pp}<span className="dim-text">pp</span></span>
      </div>
      {damageInfo && (
        <div className="move-row-dmg">
          <span className="dmg-pct mono">{damageInfo.minPct}–{damageInfo.maxPct}%</span>
          {damageInfo.effectiveness > 1 && <span className="eff super">SE</span>}
          {damageInfo.effectiveness < 1 && damageInfo.effectiveness > 0 && <span className="eff resist">NVE</span>}
          {damageInfo.effectiveness === 0 && <span className="eff immune">IMM</span>}
          {damageInfo.koChance.includes("KO") && damageInfo.koChance !== "No KO" && (
            <span className="ko-chance">{damageInfo.koChance.startsWith("Guaranteed") ? "OHKO" : "KO?"}</span>
          )}
        </div>
      )}
    </button>
  );
}

function PokemonCard({ mon, side, slot, state, onUpdate, selectedMoveIdx, onSelectMove, damagePreviews, expanded, onToggleExpand, isActive, onSetActive }) {
  if (!mon) return <div className="poke-card empty">Empty Slot</div>;

  const sideLabel = side === "ally" ? "ALLY" : "OPPONENT";
  const sideColor = side === "ally" ? "var(--ally)" : "var(--enemy)";
  const teraActive = state.teraActive;
  const displayTypes = teraActive ? [mon.teraType] : mon.types;

  return (
    <div className={`poke-card ${side} ${isActive ? "active" : ""} ${expanded ? "expanded" : ""}`}>
      {/* Header */}
      <div className="poke-header">
        <div className="poke-header-left">
          <button
            className={`active-toggle ${isActive ? "on" : ""}`}
            onClick={onSetActive}
            title="Set as primary attacker for damage preview"
          >
            <span className="active-dot"></span>
          </button>
          <div>
            <div className="poke-side-label" style={{ color: sideColor }}>{sideLabel} · SLOT {slot}</div>
            <div className="poke-name-row">
              <span className="poke-name">{mon.name}</span>
              <span className="poke-gender mono">{mon.gender}</span>
              <span className="poke-level mono">L{mon.level}</span>
            </div>
          </div>
        </div>
        <div className="poke-header-right">
          {displayTypes.map(t => <TypeBadge key={t} type={t} />)}
          {teraActive && <span className="tera-active">TERA</span>}
        </div>
      </div>

      {/* HP */}
      <HPBar current={state.hp} max={mon.stats.hp} side={side} />

      {/* Quick row: ability / item / nature / status */}
      <div className="poke-quick">
        <div className="quick-cell">
          <span className="quick-label">ABILITY</span>
          <span className="quick-val">{mon.ability}</span>
        </div>
        <div className="quick-cell">
          <span className="quick-label">ITEM</span>
          <span className="quick-val">{mon.item}</span>
        </div>
        <div className="quick-cell">
          <span className="quick-label">NATURE</span>
          <span className="quick-val">{mon.nature}</span>
        </div>
        <div className="quick-cell">
          <span className="quick-label">STATUS</span>
          <select
            className="status-select"
            value={state.status}
            onChange={(e) => onUpdate({ status: e.target.value })}
          >
            {STATUS_OPTIONS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
      </div>

      {/* Stats grid */}
      <div className="stats-grid">
        {STAT_KEYS.map(k => (
          <div key={k} className="stat-cell">
            <div className="stat-label">{STAT_LABELS[k]}</div>
            <div className="stat-val mono">{mon.stats[k]}</div>
            <div className="stat-meta mono">
              {mon.evs[k]}<span className="dim-text">/</span>{mon.ivs[k]}
            </div>
          </div>
        ))}
      </div>

      {/* Moves */}
      <div className="moves-list">
        {mon.moves.map((m, i) => (
          <MoveRow
            key={i}
            move={m}
            isSelected={selectedMoveIdx === i}
            onClick={() => onSelectMove(i)}
            damageInfo={damagePreviews && damagePreviews[i]}
            dim={!isActive}
          />
        ))}
      </div>

      {/* Expandable: stat stages + volatiles + tera + HP slider */}
      <button className="expand-toggle" onClick={onToggleExpand}>
        {expanded ? "▾ Hide controls" : "▸ Show stages & volatiles"}
      </button>

      {expanded && (
        <div className="advanced-controls">
          <div className="ctrl-section">
            <div className="ctrl-section-title">HP</div>
            <input
              type="range"
              min="0"
              max={mon.stats.hp}
              value={state.hp}
              onChange={(e) => onUpdate({ hp: Number(e.target.value) })}
              className="hp-slider"
            />
          </div>

          <div className="ctrl-section">
            <div className="ctrl-section-title">Stat Stages</div>
            <div className="stages-grid">
              {["atk", "def", "spa", "spd", "spe"].map(s => (
                <StatStageControl
                  key={s}
                  stat={s}
                  value={state.stages[s]}
                  onChange={(v) => onUpdate({ stages: { ...state.stages, [s]: v }})}
                />
              ))}
            </div>
          </div>

          <div className="ctrl-section">
            <div className="ctrl-section-title">Tera ({mon.teraType})</div>
            <button
              className={`tera-btn ${teraActive ? "on" : ""}`}
              onClick={() => onUpdate({ teraActive: !teraActive })}
              style={teraActive ? {
                borderColor: window.TYPE_COLORS[mon.teraType],
                color: window.TYPE_COLORS[mon.teraType]
              } : {}}
            >
              {teraActive ? "● Terastallized" : "○ Not Tera'd"}
            </button>
          </div>

          <div className="ctrl-section">
            <div className="ctrl-section-title">Volatile Conditions</div>
            <div className="volatiles-grid">
              {["protect", "taunt", "encore", "substitute", "leech-seed", "confusion"].map(v => (
                <label key={v} className="volatile-chip">
                  <input
                    type="checkbox"
                    checked={state.volatiles.includes(v)}
                    onChange={(e) => {
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

Object.assign(window, { PokemonCard, TypeBadge, HPBar });
