const WEATHER = [
  { id: 'none', label: 'Clear', icon: '○' },
  { id: 'sun',  label: 'Sun',   icon: '☀' },
  { id: 'rain', label: 'Rain',  icon: '☂' },
  { id: 'sand', label: 'Sand',  icon: '≋' },
  { id: 'snow', label: 'Snow',  icon: '❄' },
];

const TERRAIN = [
  { id: 'none',     label: 'None' },
  { id: 'electric', label: 'Electric' },
  { id: 'grassy',   label: 'Grassy' },
  { id: 'psychic',  label: 'Psychic' },
  { id: 'misty',    label: 'Misty' },
];

function FieldToggle({ label, active, onClick }) {
  return (
    <button className={`field-toggle ${active ? 'on' : ''}`} onClick={onClick}>
      <span className="toggle-dot" />{label}
    </button>
  );
}

export function SideStateBar({ side, state, onUpdate }) {
  return (
    <div className={`side-state ${side}`}>
      <FieldToggle label="Reflect"   active={state.reflect}      onClick={() => onUpdate({ reflect:      !state.reflect })} />
      <FieldToggle label="L. Screen" active={state.lightScreen}  onClick={() => onUpdate({ lightScreen:  !state.lightScreen })} />
      <FieldToggle label="Tailwind"  active={state.tailwind}     onClick={() => onUpdate({ tailwind:     !state.tailwind })} />
      <FieldToggle label="S. Rock"   active={state.stealthRock}  onClick={() => onUpdate({ stealthRock:  !state.stealthRock })} />
    </div>
  );
}

export default function FieldBar({ field, onUpdate }) {
  return (
    <div className="field-bar">
      <div className="field-turn">
        <div className="turn-display">
          <div className="turn-label">TURN</div>
          <div className="turn-num mono">{field.turn}</div>
        </div>
        <div className="turn-btns">
          <button className="turn-btn" onClick={() => onUpdate({ turn: Math.max(1, field.turn - 1) })}>−</button>
          <button className="turn-btn" onClick={() => onUpdate({ turn: field.turn + 1 })}>+</button>
        </div>
      </div>

      <div className="field-divider" />

      <div className="field-group">
        <div className="field-group-label">WEATHER</div>
        <div className="seg-control">
          {WEATHER.map(w => (
            <button
              key={w.id}
              className={`seg-btn ${field.weather === w.id ? 'active' : ''}`}
              onClick={() => onUpdate({ weather: w.id })}
            >
              <span className="seg-icon">{w.icon}</span>
              <span>{w.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="field-divider" />

      <div className="field-group">
        <div className="field-group-label">TERRAIN</div>
        <div className="seg-control">
          {TERRAIN.map(t => (
            <button
              key={t.id}
              className={`seg-btn ${field.terrain === t.id ? 'active' : ''}`}
              onClick={() => onUpdate({ terrain: t.id })}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="field-divider" />

      <div className="field-group">
        <div className="field-group-label">ROOMS</div>
        <div className="toggle-row">
          <FieldToggle label="Trick Room" active={field.trickRoom} onClick={() => onUpdate({ trickRoom: !field.trickRoom })} />
          <FieldToggle label="Gravity"    active={field.gravity}   onClick={() => onUpdate({ gravity:   !field.gravity })} />
        </div>
      </div>
    </div>
  );
}
