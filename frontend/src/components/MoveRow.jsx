import TypeBadge from './TypeBadge';
import { TYPE_COLORS } from '../data/typeColors';

export default function MoveRow({ move, isSelected, onClick, dim }) {
  const color = TYPE_COLORS[move.type] || '#888';
  const cat = move.category === 'Physical' ? 'PHY' : move.category === 'Special' ? 'SPE' : 'STA';
  return (
    <button
      className={`move-row ${isSelected ? 'selected' : ''} ${dim ? 'dim' : ''}`}
      style={{ '--type-color': color }}
      onClick={onClick}
    >
      <div className="move-row-main">
        <span className="move-name">{move.name}</span>
        <TypeBadge type={move.type} small />
      </div>
      <div className="move-row-meta mono">
        <span className="move-cat">{cat}</span>
        <span>{move.power || '—'}<span className="dim-text">bp</span></span>
        <span>{move.acc}<span className="dim-text">%</span></span>
        <span>{move.pp}<span className="dim-text">pp</span></span>
      </div>
    </button>
  );
}
