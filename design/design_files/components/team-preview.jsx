// Team preview bar — shows 6 mons, highlights ones on field

function TeamPreview({ side, label, roster, onField }) {
  const onFieldSet = new Set(onField);
  return (
    <div className={`team-preview ${side}`}>
      <span className="team-preview-label">{label}</span>
      <div className="team-preview-list">
        {roster.map((name, i) => {
          const active = onFieldSet.has(name);
          return (
            <div
              key={i}
              className={`team-mon ${active ? "active" : ""}`}
              title={active ? `${name} — on field` : `${name} — bench`}
            >
              <span className="team-mon-dot"></span>
              <span className="team-mon-name">{name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { TeamPreview });
