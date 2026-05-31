"use client";

interface RegimePanelProps {
  regimeInfo?: {
    label: string;
    confidence: number;
    transition_matrix: number[][];
    persistence_probability: number;
    bars_in_current_regime: number;
    structural_break: boolean;
  };
}

export default function RegimePanel({ regimeInfo }: RegimePanelProps) {
  if (!regimeInfo) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "1rem", textAlign: "center" }}>
        No HMM regime telemetry available.
      </div>
    );
  }

  const { label, confidence, transition_matrix, persistence_probability, bars_in_current_regime, structural_break } = regimeInfo;

  // Render regime label nicely
  const getRegimeColor = (name: string) => {
    switch (name) {
      case "trending_up": return "#10b981"; // success green
      case "trending_down": return "#ef4444"; // error red
      case "expansion": return "#3b82f6"; // blue
      case "panic": return "#f97316"; // orange
      case "ranging": return "#6b7280"; // slate gray
      default: return "#fbbf24";
    }
  };

  const labelColor = getRegimeColor(label);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)", fontWeight: 600, display: "block" }}>HMM CLASSIFIED REGIME</span>
          <span style={{ fontSize: "1.15rem", fontFamily: "var(--font-header)", fontWeight: 700, color: labelColor, textTransform: "uppercase" }}>
            {label.replace("_", " ")}
          </span>
        </div>
        <div style={{ textAlign: "right" }}>
          <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)", fontWeight: 600, display: "block" }}>PROBABILITY/CONFIDENCE</span>
          <span style={{ fontSize: "1.15rem", fontFamily: "var(--font-header)", fontWeight: 700, color: "#ffffff" }}>
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Structural Break CUSUM status */}
      {structural_break && (
        <div style={{ 
          background: "rgba(239, 68, 68, 0.08)", 
          border: "1px solid rgba(239, 68, 68, 0.3)", 
          borderRadius: "6px", 
          padding: "0.4rem 0.6rem", 
          fontSize: "0.7rem", 
          color: "var(--error)",
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          gap: "0.4rem"
        }}>
          ⚠️ CUSUM STRUCTURAL SHIFT DETECTED
        </div>
      )}

      {/* Numerical Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
        <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-color)", padding: "0.4rem 0.6rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>BARS PERSISTED</span>
          <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>{bars_in_current_regime} bars</span>
        </div>
        <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-color)", padding: "0.4rem 0.6rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>STATE PERSISTENCE PROB</span>
          <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>{(persistence_probability * 100).toFixed(1)}%</span>
        </div>
      </div>

      {/* Transition Matrix visual layout */}
      {transition_matrix && (
        <div>
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", fontWeight: 600, display: "block", marginBottom: "0.3rem" }}>HMM TRANSITION PROBABILITY MATRIX</span>
          <div style={{ display: "flex", flexDirection: "column", gap: "2px", fontFamily: "monospace", fontSize: "0.7rem" }}>
            {transition_matrix.map((row, rIdx) => (
              <div key={rIdx} style={{ display: "flex", gap: "2px" }}>
                {row.map((val, cIdx) => (
                  <div 
                    key={cIdx} 
                    style={{ 
                      flex: 1, 
                      textAlign: "center", 
                      padding: "0.25rem 0.1rem", 
                      background: `rgba(99, 102, 241, ${val * 0.25})`, 
                      border: "1px solid rgba(255,255,255,0.03)", 
                      color: val > 0.4 ? "#ffffff" : "var(--text-secondary)",
                      fontWeight: val > 0.4 ? 600 : 400,
                      borderRadius: "3px"
                    }}
                  >
                    {val.toFixed(2)}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
