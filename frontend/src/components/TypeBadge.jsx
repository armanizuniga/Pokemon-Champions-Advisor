import { TYPE_COLORS } from '../data/typeColors';

export default function TypeBadge({ type, small }) {
  const color = TYPE_COLORS[type] || '#888';
  return (
    <span
      className="type-badge"
      style={{
        background: `${color}28`,
        color,
        border: `1px solid ${color}66`,
        fontSize: small ? '9px' : '10px',
        padding: small ? '1px 5px' : '2px 7px',
      }}
    >
      {type.toUpperCase()}
    </span>
  );
}
