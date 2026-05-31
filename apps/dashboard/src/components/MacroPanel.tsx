"use client";

interface MacroPanelProps {
  macroContext?: Record<string, number>;
}

export default function MacroPanel({ macroContext }: MacroPanelProps) {
  if (!macroContext) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "1rem", textAlign: "center" }}>
        Loading global macro context parameters...
      </div>
    );
  }

  // Extract variables
  const { dxy = 104.0, dxy_prev = 104.0, us10y = 4.5, us10y_prev = 4.5, vix = 18.0, vix_prev = 18.0, usdt_dominance = 6.5, usdt_dominance_prev = 6.5 } = macroContext;

  const renderTrend = (cur: number, prev: number) => {
    const diff = cur - prev;
    if (diff > 0.001) return <span style={{ color: "var(--error)", fontSize: "0.7rem" }}>▲ (+{(diff).toFixed(2)})</span>;
    if (diff < -0.001) return <span style={{ color: "var(--success)", fontSize: "0.7rem" }}>▼ ({(diff).toFixed(2)})</span>;
    return <span style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>■ (0.00)</span>;
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
        {/* DXY Card */}
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.5rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>DXY DOLLAR INDEX</span>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>{dxy.toFixed(2)}</span>
            {renderTrend(dxy, dxy_prev)}
          </div>
        </div>

        {/* US 10Y Yield Card */}
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.5rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>US 10Y BOND YIELD</span>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>{us10y.toFixed(2)}%</span>
            {renderTrend(us10y, us10y_prev)}
          </div>
        </div>

        {/* VIX Card */}
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.5rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>VIX FEAR INDEX</span>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>{vix.toFixed(1)}</span>
            {renderTrend(vix, vix_prev)}
          </div>
        </div>

        {/* USDT Dominance Card */}
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.5rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>USDT DOMINANCE</span>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <span style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>{usdt_dominance.toFixed(2)}%</span>
            {renderTrend(usdt_dominance, usdt_dominance_prev)}
          </div>
        </div>
      </div>
    </div>
  );
}
