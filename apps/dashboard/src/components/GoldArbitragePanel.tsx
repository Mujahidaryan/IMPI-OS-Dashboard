"use client";

interface GoldArbitragePanelProps {
  exnessTick?: { last: number; bid: number; ask: number };
  binanceTick?: { last: number };
  divergence?: number; // 0.0 – 1.0
}

export default function GoldArbitragePanel({ exnessTick, binanceTick, divergence }: GoldArbitragePanelProps) {
  if (!exnessTick || !binanceTick) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "1.5rem", textAlign: "center" }}>
        Waiting for tick feeds to evaluate gold arbitrage basis spread...
      </div>
    );
  }

  const divPct = (divergence || 0) * 100;
  const isAnomaly = divPct > 0.3;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.6rem 0.8rem", borderRadius: "8px" }}>
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", display: "block" }}>EXNESS SPOT CFD</span>
          <span style={{ fontSize: "1.2rem", fontFamily: "var(--font-header)", fontWeight: 700, color: "var(--gold)" }}>
            ${exnessTick.last.toFixed(2)}
          </span>
          <div style={{ display: "flex", gap: "0.4rem", fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
            <span>B: ${exnessTick.bid.toFixed(2)}</span>
            <span>•</span>
            <span>A: ${exnessTick.ask.toFixed(2)}</span>
          </div>
        </div>

        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.6rem 0.8rem", borderRadius: "8px" }}>
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", display: "block" }}>BINANCE FUTURES</span>
          <span style={{ fontSize: "1.2rem", fontFamily: "var(--font-header)", fontWeight: 700, color: "#ffffff" }}>
            ${binanceTick.last.toFixed(2)}
          </span>
          <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
            Perpetual contracts
          </div>
        </div>
      </div>

      {/* Divergence and alarm banner */}
      <div style={{
        background: isAnomaly ? "rgba(239, 68, 68, 0.08)" : "rgba(16, 185, 129, 0.06)",
        border: `1px solid ${isAnomaly ? "rgba(239, 68, 68, 0.3)" : "rgba(16, 185, 129, 0.2)"}`,
        borderRadius: "8px",
        padding: "0.75rem",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }}>
        <div>
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", display: "block" }}>CROSS-EXCHANGE DIVERGENCE</span>
          <span style={{ 
            fontSize: "1.1rem", 
            fontFamily: "var(--font-header)", 
            fontWeight: 700, 
            color: isAnomaly ? "var(--error)" : "var(--success)" 
          }}>
            {divPct.toFixed(3)}%
          </span>
        </div>
        <div style={{ 
          fontSize: "0.7rem", 
          fontWeight: 700, 
          color: isAnomaly ? "var(--error)" : "var(--success)",
          textTransform: "uppercase",
          letterSpacing: "0.05em"
        }}>
          {isAnomaly ? "⚠️ ARB ANOMALY DETECTED" : "✓ INTEGRITY GREEN"}
        </div>
      </div>

      {isAnomaly && (
        <p style={{ fontSize: "0.65rem", color: "var(--text-secondary)", fontStyle: "italic", lineHeight: 1.3 }}>
          * Divergence exceeds 0.3% limit. Bayesian fusion engine has automatically applied a confidence decay penalty to fused probabilities.
        </p>
      )}
    </div>
  );
}
