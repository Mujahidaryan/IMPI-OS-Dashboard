"use client";

interface RiskPanelProps {
  riskData?: {
    account_balance: number;
    peak_balance: number;
    drawdown_pct: number;
    trading_halted: boolean;
    consecutive_losses: number;
    correlation_exposure: Record<string, number>;
  };
}

export default function RiskPanel({ riskData }: RiskPanelProps) {
  if (!riskData) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "1.5rem", textAlign: "center" }}>
        Loading risk guard metrics...
      </div>
    );
  }

  const { account_balance, peak_balance, drawdown_pct, trading_halted, consecutive_losses, correlation_exposure } = riskData;

  const isHalted = trading_halted || drawdown_pct > 5.0; // Assume 5% is hard halt

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {/* Account stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.5rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>ACCOUNT BALANCE</span>
          <span style={{ fontSize: "1.1rem", fontFamily: "var(--font-header)", fontWeight: 700, color: "#ffffff" }}>
            ${account_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.5rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>PEAK VALUE</span>
          <span style={{ fontSize: "1.1rem", fontFamily: "var(--font-header)", fontWeight: 700, color: "var(--text-secondary)" }}>
            ${peak_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>
      </div>

      {/* Drawdown state */}
      <div style={{
        background: isHalted ? "rgba(239, 68, 68, 0.08)" : "rgba(255, 255, 255, 0.01)",
        border: `1px solid ${isHalted ? "rgba(239, 68, 68, 0.3)" : "var(--border-color)"}`,
        borderRadius: "8px",
        padding: "0.75rem",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }}>
        <div>
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", display: "block" }}>PEAK-TO-VALLEY DRAWDOWN</span>
          <span style={{ 
            fontSize: "1.15rem", 
            fontFamily: "var(--font-header)", 
            fontWeight: 700, 
            color: isHalted ? "var(--error)" : "var(--success)" 
          }}>
            {drawdown_pct.toFixed(2)}%
          </span>
        </div>
        <div style={{ 
          fontSize: "0.7rem", 
          fontWeight: 700, 
          color: isHalted ? "var(--error)" : "var(--success)",
          textTransform: "uppercase"
        }}>
          {isHalted ? "🔴 HALTED" : "✓ GUARD ENGAGED"}
        </div>
      </div>

      {/* Exposure checklist */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.7rem", color: "var(--text-secondary)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Consecutive Loss Counter</span>
          <span style={{ color: consecutive_losses >= 3 ? "var(--warning)" : "var(--success)", fontWeight: 600 }}>
            {consecutive_losses} / 5 max
          </span>
        </div>

        {/* Per-symbol exposure limits */}
        {Object.entries(correlation_exposure).map(([sym, corr]) => (
          <div key={sym} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Exposure Risk ({sym.split("_")[0]})</span>
            <span style={{ color: corr > 2.0 ? "var(--warning)" : "var(--success)", fontWeight: 600 }}>
              {corr.toFixed(2)}% (Max 3%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
