"use client";

interface StrategyBreakdownProps {
  contributions?: Record<string, number>;
}

export default function StrategyBreakdown({ contributions }: StrategyBreakdownProps) {
  if (!contributions) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "1.5rem", textAlign: "center" }}>
        No strategy contribution data available.
      </div>
    );
  }

  // Find max contribution for relative bar widths
  const items = Object.entries(contributions).map(([name, val]) => ({
    name: name.replace("_", " "),
    value: val,
  }));

  const maxVal = Math.max(...items.map((i) => i.value), 1.0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      {items.map((item, index) => {
        const widthPct = (item.value / maxVal) * 100;
        
        return (
          <div key={index} style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "0.75rem" }}>
              <span style={{ textTransform: "capitalize", fontWeight: 500, color: "var(--text-primary)" }}>{item.name}</span>
              <span style={{ fontWeight: 600, color: "#ffffff", fontFamily: "monospace" }}>{item.value.toFixed(2)}</span>
            </div>
            
            {/* Visual Bar Indicator */}
            <div style={{ width: "100%", height: "6px", background: "rgba(255,255,255,0.02)", borderRadius: "3px", overflow: "hidden" }}>
              <div 
                style={{ 
                  width: `${widthPct}%`, 
                  height: "100%", 
                  background: "linear-gradient(90deg, var(--accent-color), #818cf8)", 
                  borderRadius: "3px",
                  transition: "width 0.4s ease"
                }} 
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
