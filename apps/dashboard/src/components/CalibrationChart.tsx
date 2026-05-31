"use client";

interface CalibrationChartProps {
  calibrationData?: {
    curve: Array<{
      bin: number;
      range: string;
      count: number;
      mean_predicted: number;
      actual_frequency: number;
    }>;
    total_samples: number;
  };
  metrics?: {
    brier_score?: number | null;
    ece?: number | null;
  };
}

export default function CalibrationChart({ calibrationData, metrics }: CalibrationChartProps) {
  const curve = calibrationData?.curve || [];
  
  // Custom SVG rendering of the calibration reliability curve
  // Dimensions
  const width = 250;
  const height = 150;
  const padding = 25;

  const getX = (val: number) => padding + (val * (width - 2 * padding));
  const getY = (val: number) => height - padding - (val * (height - 2 * padding));

  // Ideal calibration reference line (y = x)
  const idealPath = `M ${getX(0)} ${getY(0)} L ${getX(1)} ${getY(1)}`;

  // Actual calibration line
  const actualPoints = curve
    .filter((b) => b.count > 0)
    .map((b) => ({
      x: getX(b.mean_predicted),
      y: getY(b.actual_frequency)
    }));

  const actualPath = actualPoints.length > 0
    ? `M ${actualPoints[0].x} ${actualPoints[0].y} ` + 
      actualPoints.slice(1).map((p) => `L ${p.x} ${p.y}`).join(" ")
    : "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      {/* Metric summary */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.4rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>BRIER SCORE (CALIB MSE)</span>
          <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#ffffff", fontFamily: "monospace" }}>
            {metrics?.brier_score !== undefined && metrics?.brier_score !== null ? metrics.brier_score.toFixed(4) : "0.2500"}
          </span>
        </div>
        <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", padding: "0.4rem 0.65rem", borderRadius: "6px" }}>
          <span style={{ fontSize: "0.6rem", color: "var(--text-secondary)", display: "block" }}>EXPECTED CALIB ERROR (ECE)</span>
          <span style={{ fontSize: "0.95rem", fontWeight: 700, color: (metrics?.ece || 0) > 0.10 ? "var(--warning)" : "var(--success)", fontFamily: "monospace" }}>
            {metrics?.ece !== undefined && metrics?.ece !== null ? `${(metrics.ece * 100).toFixed(2)}%` : "0.00%"}
          </span>
        </div>
      </div>

      {/* Reliability Curve SVG */}
      <div style={{ display: "flex", justifyContent: "center", padding: "0.25rem 0", background: "rgba(255,255,255,0.01)", border: "1px solid var(--border-color)", borderRadius: "8px" }}>
        <svg width={width} height={height} style={{ overflow: "visible" }}>
          {/* Grid lines */}
          <line x1={getX(0.5)} y1={getY(0)} x2={getX(0.5)} y2={getY(1)} stroke="rgba(255,255,255,0.03)" strokeWidth="1" strokeDasharray="3" />
          <line x1={getX(0)} y1={getY(0.5)} x2={getX(1)} y2={getY(0.5)} stroke="rgba(255,255,255,0.03)" strokeWidth="1" strokeDasharray="3" />

          {/* Reference Line (y=x, Perfect Calibration) */}
          <path d={idealPath} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1.5" strokeDasharray="4" />
          
          {/* Actual Calibration Curve */}
          {actualPath && (
            <path d={actualPath} fill="none" stroke="var(--accent-color)" strokeWidth="2.5" />
          )}

          {/* Data Points */}
          {actualPoints.map((pt, idx) => (
            <circle key={idx} cx={pt.x} cy={pt.y} r="3" fill="#ffffff" stroke="var(--accent-color)" strokeWidth="1.5" />
          ))}

          {/* Axis Labels */}
          <text x={width / 2} y={height - 2} fill="var(--text-secondary)" fontSize="7" textAnchor="middle">
            Predicted Probability
          </text>
          <text x="2" y={height / 2} fill="var(--text-secondary)" fontSize="7" textAnchor="middle" transform={`rotate(-90 2 ${height/2})`}>
            Actual Frequency
          </text>

          {/* Boundaries labels */}
          <text x={getX(0)} y={getY(0) + 10} fill="var(--text-muted)" fontSize="6" textAnchor="middle">0.0</text>
          <text x={getX(1)} y={getY(0) + 10} fill="var(--text-muted)" fontSize="6" textAnchor="middle">1.0</text>
          <text x={getX(0) - 8} y={getY(0)} fill="var(--text-muted)" fontSize="6" textAnchor="end">0.0</text>
          <text x={getX(0) - 8} y={getY(1) + 4} fill="var(--text-muted)" fontSize="6" textAnchor="end">1.0</text>
        </svg>
      </div>

      <div style={{ fontSize: "0.6rem", color: "var(--text-muted)", textAlign: "center" }}>
        * Reliability curve maps forecast accuracy on {calibrationData?.total_samples || 0} history samples.
      </div>
    </div>
  );
}
