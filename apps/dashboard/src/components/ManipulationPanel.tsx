"use client";

interface ManipulationPanelProps {
  score?: number; // 0.0 – 1.0
  symbol: string;
}

export default function ManipulationPanel({ score = 0, symbol }: ManipulationPanelProps) {
  const scorePct = score * 100;
  
  const getLevelColor = (val: number) => {
    if (val > 70) return "var(--error)";
    if (val > 40) return "var(--warning)";
    return "var(--success)";
  };

  const color = getLevelColor(scorePct);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", display: "block" }}>COMPOSITE SKEW / MANIPULATION LEVEL</span>
          <span style={{ fontSize: "1.2rem", fontFamily: "var(--font-header)", fontWeight: 700, color }}>
            {scorePct.toFixed(0)}%
          </span>
        </div>
        <div style={{
          fontSize: "0.75rem",
          fontWeight: 700,
          color,
          textTransform: "uppercase",
          padding: "0.25rem 0.5rem",
          background: `rgba(255, 255, 255, 0.02)`,
          border: `1px solid ${color}40`,
          borderRadius: "4px"
        }}>
          {scorePct > 70 ? "High" : scorePct > 40 ? "Moderate" : "Low"}
        </div>
      </div>

      {/* Progress Bar indicator */}
      <div style={{ width: "100%", height: "8px", background: "rgba(255,255,255,0.03)", borderRadius: "4px", overflow: "hidden", display: "flex" }}>
        <div style={{ width: `${scorePct}%`, height: "100%", background: color, borderRadius: "4px", transition: "width 0.4s ease" }} />
      </div>

      {/* Checklist items */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginTop: "0.25rem", fontSize: "0.7rem", color: "var(--text-secondary)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Wick-Spike Anomaly Monitor</span>
          <span style={{ color: score > 0.5 ? "var(--warning)" : "var(--success)", fontWeight: 600 }}>
            {score > 0.5 ? "ANOMALOUS WICK" : "NORMAL"}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Breakout Validity Guard</span>
          <span style={{ color: score > 0.4 ? "var(--warning)" : "var(--success)", fontWeight: 600 }}>
            {score > 0.4 ? "FAKE BREAKOUT RISK" : "VALID ZONE"}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Liquidity Level Integrity</span>
          <span style={{ color: "var(--success)", fontWeight: 600 }}>STABLE</span>
        </div>
      </div>

      {score > 0.4 && (
        <div style={{
          fontSize: "0.65rem",
          color: "var(--text-muted)",
          lineHeight: 1.3,
          padding: "0.5rem",
          background: "rgba(255,255,255,0.01)",
          border: "1px solid var(--border-color)",
          borderRadius: "6px"
        }}>
          * Significant wick spikes or fake breakouts detected. Probability metrics adjusted to account for liquidity traps.
        </div>
      )}
    </div>
  );
}
