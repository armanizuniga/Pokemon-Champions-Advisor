import { useState } from 'react';

function Section({ title, children }) {
  return (
    <div className="analysis-section">
      <div className="analysis-section-title">{title}</div>
      <div className="analysis-section-body">{children}</div>
    </div>
  );
}

function Reasoning({ text }) {
  if (!text) return null;
  const paragraphs = text.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
  return (
    <div className="reasoning-card">
      {paragraphs.map((p, i) => <p key={i} className="reasoning-para">{p}</p>)}
    </div>
  );
}

function SpeedOrder({ allies, opponents, trickRoom }) {
  const all = [
    ...allies.map(m => ({ name: m.name, spe: m.baseStats?.spe ?? 0, side: 'ally' })),
    ...opponents.map(m => ({ name: m.name, spe: m.baseStats?.spe ?? 0, side: 'opp' })),
  ];
  if (!all.length) return <div className="speed-empty">No active Pokémon</div>;

  const sorted = [...all].sort((a, b) => trickRoom ? a.spe - b.spe : b.spe - a.spe);
  return (
    <div className="speed-order-card">
      {trickRoom && <div className="speed-tr-note">Trick Room active — slowest moves first</div>}
      <div className="speed-order-list">
        {sorted.map((m, i) => (
          <div key={i} className={`speed-entry ${m.side === 'ally' ? 'speed-ally' : 'speed-opp'}`}>
            <span className="speed-rank mono">{i + 1}</span>
            <span className="speed-name">{m.name}</span>
            <span className="speed-stat mono">{m.spe}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DamageMatrix({ rows }) {
  if (!rows?.length) return null;

  const groups = [];
  const seen = new Map();
  for (const row of rows) {
    const key = `${row.side}::${row.attacker}`;
    if (!seen.has(key)) {
      const g = { attacker: row.attacker, side: row.side, moves: [] };
      seen.set(key, g);
      groups.push(g);
    }
    seen.get(key).moves.push(row);
  }

  return (
    <table className="dmg-table">
      <thead>
        <tr>
          <th>Move</th><th>Target</th><th>% HP</th><th>Result</th>
        </tr>
      </thead>
      <tbody>
        {groups.map(group => (
          <>
            <tr key={`hdr-${group.side}-${group.attacker}`} className="dmg-attacker-row">
              <td colSpan={4}>
                <span className={group.side === 'opponent' ? 'dmg-opp-label' : 'dmg-your-label'}>
                  {group.side === 'opponent' ? 'OPP' : 'YOU'}
                </span>
                {' '}{group.attacker}
              </td>
            </tr>
            {[...group.moves].sort((a, b) => b.pct_hi - a.pct_hi).map((row, i) => (
              <tr key={`${group.attacker}-${i}`} className="dmg-move-row">
                <td>
                  {row.move}
                  {row.friendly_fire && <span className="dmg-ff" title="Friendly fire"> ⚠</span>}
                </td>
                <td className="dmg-defender">{row.defender}</td>
                <td className="mono">{row.pct_lo}–{row.pct_hi}%</td>
                <td>
                  {row.is_ohko  && <span className="dmg-ohko">OHKO</span>}
                  {!row.is_ohko && row.is_2hko && <span className="dmg-2hko">2HKO</span>}
                  {!row.is_ohko && !row.is_2hko && <span className="dmg-neutral">—</span>}
                </td>
              </tr>
            ))}
          </>
        ))}
      </tbody>
    </table>
  );
}

export default function AnalysisPanel({ buildPayload, allies, opponents, field }) {
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [error,  setError]  = useState(null);

  async function handleSubmit() {
    setStatus('loading');
    setError(null);
    setResult(null);
    try {
      const payload = buildPayload();
      const res = await fetch('/api/analyze', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setResult(await res.json());
      setStatus('result');
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  }

  const aliveAllies = allies.filter(a => a).length;
  const rec = result?.recommendation;

  return (
    <div className="analysis-panel">
      <div className="analysis-header">
        <div>
          <div className="analysis-title">COACH ANALYSIS</div>
          <div className="analysis-sub">Turn {field.turn} · {aliveAllies}v2</div>
        </div>
        <button className="submit-btn" onClick={handleSubmit} disabled={status === 'loading'}>
          {status === 'loading'
            ? <><span className="spinner" />Analyzing…</>
            : <>▶ Send to Claude</>}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {status === 'result' && rec && (
        <div className="analysis-body">
          <Section title="Recommended Actions">
            <div className="rec-card">
              <div className="rec-mon">{allies[0]?.name}</div>
              <div className="rec-action">{rec.action_1}</div>
            </div>
            <div style={{ height: 6 }} />
            <div className="rec-card">
              <div className="rec-mon">{allies[1]?.name}</div>
              <div className="rec-action">{rec.action_2}</div>
            </div>
          </Section>

          {rec.win_condition && (
            <Section title="Win Condition">
              <div className="win-cond-card">{rec.win_condition}</div>
            </Section>
          )}

          {rec.board_state_summary && (
            <Section title="Field State">
              <div className="board-state-card">{rec.board_state_summary}</div>
            </Section>
          )}

          <Section title="Threat Assessment">
            <div className="threat-card">{rec.threat_assessment}</div>
          </Section>

          <Section title="Contingency">
            <div className="contingency-card">{rec.contingency}</div>
          </Section>

          <Section title="Speed Order">
            <SpeedOrder allies={allies} opponents={opponents} trickRoom={field.trickRoom} />
          </Section>

          <Section title="Reasoning">
            <Reasoning text={rec.reasoning} />
          </Section>

          {result.damage_matrix?.length > 0 && (
            <Section title="Damage Calc">
              <DamageMatrix rows={result.damage_matrix} />
            </Section>
          )}
        </div>
      )}

      {status === 'idle' && (
        <div className="empty-analysis">
          <div className="empty-icon">◇</div>
          <div className="empty-text">
            Adjust the board state, then send it to Claude for turn-by-turn recommendations.
          </div>
        </div>
      )}
    </div>
  );
}
