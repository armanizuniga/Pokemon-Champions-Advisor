import { useState } from 'react';

function Section({ title, children }) {
  return (
    <div className="analysis-section">
      <div className="analysis-section-title">{title}</div>
      <div className="analysis-section-body">{children}</div>
    </div>
  );
}

export default function AnalysisPanel({ buildPayload, allies, field }) {
  const [status, setStatus]   = useState('idle');
  const [result, setResult]   = useState(null);
  const [error, setError]     = useState(null);

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

  return (
    <div className="analysis-panel">
      <div className="analysis-header">
        <div>
          <div className="analysis-title">COACH ANALYSIS</div>
          <div className="analysis-sub">Turn {field.turn} · {aliveAllies}v2</div>
        </div>
      </div>

      <button className="submit-btn" onClick={handleSubmit} disabled={status === 'loading'}>
        {status === 'loading'
          ? <><span className="spinner" />Analyzing board state…</>
          : <>▶ Send to Claude</>}
      </button>

      {error && <div className="error-box">{error}</div>}

      {status === 'result' && result && (
        <div className="analysis-body">
          <Section title="Recommended Actions">
            <div className="rec-card">
              <div className="rec-mon">{allies[0]?.name}</div>
              <div className="rec-action">{result.recommendation.action_1}</div>
            </div>
            <div style={{ height: 6 }} />
            <div className="rec-card">
              <div className="rec-mon">{allies[1]?.name}</div>
              <div className="rec-action">{result.recommendation.action_2}</div>
            </div>
          </Section>

          <Section title="Priority Order">
            <div className="priority-card">{result.recommendation.priority_order}</div>
          </Section>

          <Section title="Threat Assessment">
            <div className="threat-card">{result.recommendation.threat_assessment}</div>
          </Section>

          <Section title="Contingency">
            <div className="contingency-card">{result.recommendation.contingency}</div>
          </Section>

          <Section title="Reasoning">
            <div className="reasoning-card">{result.recommendation.reasoning}</div>
          </Section>

          {result.damage_matrix?.length > 0 && (
            <Section title="Damage Matrix">
              <table className="dmg-table">
                <thead>
                  <tr>
                    <th>Side</th><th>Attacker</th><th>Move</th><th>Defender</th>
                    <th>% HP</th><th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {result.damage_matrix.map((row, i) => (
                    <tr key={i}>
                      <td className={row.side === 'opponent' ? 'dmg-opp' : 'dmg-your'}>
                        {row.side === 'opponent' ? 'opp' : 'you'}
                      </td>
                      <td>{row.attacker}</td>
                      <td>
                        {row.move}
                        {row.friendly_fire && <span className="dmg-ff"> ⚠</span>}
                      </td>
                      <td>{row.defender}</td>
                      <td className="mono">{row.pct_lo}–{row.pct_hi}%</td>
                      <td>
                        {row.is_ohko  && <span className="dmg-ohko">OHKO</span>}
                        {!row.is_ohko && row.is_2hko && <span className="dmg-2hko">2HKO</span>}
                        {!row.is_ohko && !row.is_2hko && <span style={{ color: 'var(--text-faint)' }}>—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}
        </div>
      )}

      {status === 'idle' && (
        <div className="empty-analysis">
          <div className="empty-icon">◇</div>
          <div className="empty-text">
            Adjust the board state, then send it to Claude for turn-by-turn recommendations with damage calcs, threats, and priority order.
          </div>
        </div>
      )}
    </div>
  );
}
