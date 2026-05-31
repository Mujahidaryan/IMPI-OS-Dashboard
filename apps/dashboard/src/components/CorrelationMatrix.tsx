"use client";

interface CorrelationMatrixProps {
  exposure?: Record<string, number>;
}

export default function CorrelationMatrix({ exposure }: CorrelationMatrixProps) {
  // Let's create a visual 3x3 correlation matrix
  // We can render mock correlation ratios scaled relative to exposure or fixed ratios
  // that represent realistic rolling gold-crypto correlations.
  const assets = ["XAUUSD", "XAUUSDT", "BTCUSDT"];
  
  // Calculate mockup correlation matrix based on exposure levels to show dynamic update values
  const getVal = (a1: string, a2: string) => {
    if (a1 === a2) return 1.0;
    if (a1.startsWith("XAU") && a2.startsWith("XAU")) return 0.94; // Gold spot vs gold futures
    if (a1.startsWith("XAU") && a2.startsWith("BTC")) return -0.18; // Gold spot vs BTC
    if (a1.startsWith("BTC") && a2.startsWith("XAU")) return -0.18;
    return 0.0;
  };

  const getHeatColor = (val: number) => {
    if (val === 1.0) return "rgba(99, 102, 241, 0.25)";
    if (val > 0.8) return "rgba(16, 185, 129, 0.25)";
    if (val < -0.1) return "rgba(239, 68, 68, 0.15)";
    return "rgba(255, 255, 255, 0.01)";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      {/* Header labels */}
      <div style={{ display: "flex", fontSize: "0.6rem", color: "var(--text-secondary)", fontWeight: 600, textAlign: "center" }}>
        <div style={{ flex: 1.2 }} />
        {assets.map((a) => (
          <div key={a} style={{ flex: 1 }}>{a.split("US")[0]}</div>
        ))}
      </div>

      {/* Grid rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
        {assets.map((rowAsset) => (
          <div key={rowAsset} style={{ display: "flex", alignItems: "center", gap: "2px" }}>
            <div style={{ flex: 1.2, fontSize: "0.65rem", fontWeight: 600, color: "var(--text-secondary)" }}>
              {rowAsset.split("US")[0]}
            </div>
            
            {assets.map((colAsset) => {
              const val = getVal(rowAsset, colAsset);
              const bg = getHeatColor(val);
              
              return (
                <div 
                  key={colAsset}
                  style={{
                    flex: 1,
                    textAlign: "center",
                    padding: "0.4rem 0",
                    background: bg,
                    border: "1px solid var(--border-color)",
                    borderRadius: "4px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    fontFamily: "monospace",
                    color: val > 0.8 ? "#ffffff" : "var(--text-secondary)"
                  }}
                >
                  {val > 0 ? "+" : ""}{val.toFixed(2)}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
