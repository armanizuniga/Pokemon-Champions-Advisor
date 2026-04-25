export default function TeamPreview({ side, label, roster, onField }) {
  const onFieldSet = new Set(onField);
  return (
    <div className={`team-preview ${side}`}>
      <span className="team-preview-label">{label}</span>
      <div className="team-preview-list">
        {roster.map((name, i) => (
          <div key={i} className={`team-mon ${onFieldSet.has(name) ? 'active' : ''}`}>
            <span className="team-mon-dot" />
            <span>{name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
