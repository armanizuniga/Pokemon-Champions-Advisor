// Analysis panel — submits state to Claude and shows recommendations

function AnalysisPanel({ buildPrompt, gameState, onClose }) {
  const [analysis, setAnalysis] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [verbosity, setVerbosity] = React.useState("balanced");

  const requestAnalysis = async () => {
    setLoading(true);
    setError(null);
    setAnalysis(null);
    try {
      const prompt = buildPrompt(verbosity);
      const result = await window.claude.complete({
        messages: [{ role: "user", content: prompt }]
      });
      // Try to parse as JSON
      let parsed;
      try {
        const match = result.match(/\{[\s\S]*\}/);
        parsed = JSON.parse(match ? match[0] : result);
      } catch (e) {
        parsed = { raw: result };
      }
      setAnalysis(parsed);
    } catch (e) {
      setError(e.message || "Analysis failed");
    }
    setLoading(false);
  };

  return (
    <div className="analysis-panel">
      <div className="analysis-header">
        <div>
          <div className="analysis-title">COACH ANALYSIS</div>
          <div className="analysis-sub">Turn {gameState.field.turn} · {gameState.allies.filter(a => a && gameState.monStates[a.id]?.hp > 0).length}v{gameState.opponents.filter(o => o && gameState.monStates[o.id]?.hp > 0).length}</div>
        </div>
        {onClose && <button className="close-btn" onClick={onClose}>×</button>}
      </div>

      <div className="verbosity-row">
        <span className="verbosity-label">DEPTH</span>
        <div className="seg-control small">
          {["concise", "balanced", "deep"].map(v => (
            <button
              key={v}
              className={`seg-btn ${verbosity === v ? "active" : ""}`}
              onClick={() => setVerbosity(v)}
            >{v}</button>
          ))}
        </div>
      </div>

      <button
        className="submit-btn"
        onClick={requestAnalysis}
        disabled={loading}
      >
        {loading ? (
          <><span className="spinner"></span>Analyzing board state…</>
        ) : (
          <>▶ Submit board state for analysis</>
        )}
      </button>

      {error && <div className="error-box">{error}</div>}

      {analysis && (
        <div className="analysis-body">
          {analysis.raw ? (
            <pre className="raw-analysis">{analysis.raw}</pre>
          ) : (
            <>
              {analysis.summary && (
                <Section title="Read of the board">
                  <p>{analysis.summary}</p>
                </Section>
              )}

              {analysis.threats && analysis.threats.length > 0 && (
                <Section title="Threat assessment">
                  {analysis.threats.map((t, i) => (
                    <div key={i} className="threat-row">
                      <div className="threat-target">{t.from}</div>
                      <div className="threat-desc">{t.description}</div>
                    </div>
                  ))}
                </Section>
              )}

              {analysis.recommendations && analysis.recommendations.length > 0 && (
                <Section title="Recommended plays">
                  {analysis.recommendations.map((r, i) => (
                    <div key={i} className="rec-card">
                      <div className="rec-header">
                        <span className="rec-mon">{r.pokemon}</span>
                        <span className="rec-arrow">→</span>
                        <span className="rec-move">{r.move}</span>
                        {r.target && <span className="rec-target">@ {r.target}</span>}
                      </div>
                      {r.reasoning && <div className="rec-reason">{r.reasoning}</div>}
                      {r.damage && <div className="rec-dmg mono">{r.damage}</div>}
                    </div>
                  ))}
                </Section>
              )}

              {analysis.win_condition && (
                <Section title="Win condition">
                  <p>{analysis.win_condition}</p>
                </Section>
              )}

              {analysis.lesson && (
                <Section title="Teaching note">
                  <p className="lesson">{analysis.lesson}</p>
                </Section>
              )}
            </>
          )}
        </div>
      )}

      {!analysis && !loading && (
        <div className="empty-analysis">
          <div className="empty-icon">◇</div>
          <div className="empty-text">Adjust the board state above, then submit for a turn-by-turn read with damage calcs, threats, and a recommended play.</div>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="analysis-section">
      <div className="analysis-section-title">{title}</div>
      <div className="analysis-section-body">{children}</div>
    </div>
  );
}

Object.assign(window, { AnalysisPanel });
