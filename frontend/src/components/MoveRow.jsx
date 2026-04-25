import TypeBadge from './TypeBadge';
import { TYPE_COLORS } from '../data/typeColors';

export default function MoveRow({ move, isSelected, onClick, dim }) {
  const name     = typeof move === 'string' ? move : move.name;
  const type     = typeof move === 'string' ? null : (move.type ?? null);
  const category = typeof move === 'string' ? null : (move.category ?? null);
  const color    = TYPE_COLORS[type] || '#888';
  const cat      = category === 'Physical' ? 'PHY' : category === 'Special' ? 'SPE' : category === 'Status' ? 'STA' : null;

  return (
    <button
      className={`move-row ${isSelected ? 'selected' : ''} ${dim ? 'dim' : ''}`}
      style={{ '--type-color': color }}
      onClick={onClick}
    >
      <div className="move-row-main">
        <span className="move-name">{name}</span>
        {type && <TypeBadge type={type} small />}
      </div>
      {cat && (
        <div className="move-row-meta mono">
          <span className="move-cat">{cat}</span>
          <span>{move.power || '—'}<span className="dim-text">bp</span></span>
          <span>{move.acc}<span className="dim-text">%</span></span>
          <span>{move.pp}<span className="dim-text">pp</span></span>
        </div>
      )}
    </button>
  );
}
