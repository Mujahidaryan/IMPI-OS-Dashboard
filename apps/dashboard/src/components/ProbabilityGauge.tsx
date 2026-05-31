"use client";

import { useMemo } from "react";

interface ProbabilityGaugeProps {
  probability: number; // 0 - 100
  ciLower: number;
  ciUpper: number;
  direction: string; // "long" | "short" | "reversal" | "breakout"
  strength: string; // "insufficient" | "low" | "medium" | "high" | "very_high"
}

export default function ProbabilityGauge({
  probability,
  ciLower,
  ciUpper,
  direction,
  strength,
}: ProbabilityGaugeProps) {
  // SVG semicircular layout params
  const radius = 80;
  const strokeWidth = 12;
  const center = 100;
  const startAngle = -180; // half circle starts on left
  const endAngle = 0; // half circle ends on right
  const angleRange = 180;

  // Map values to polar path coordinates
  const getCoordinates = (val: number) => {
    // val is in [0, 100], map to angle in range [-180, 0]
    const percent = Math.min(Math.max(val, 0), 100) / 100;
    const angle = startAngle + percent * angleRange;
    const rad = (angle * Math.PI) / 180;
    const x = center + radius * Math.cos(rad);
    const y = center + radius * Math.sin(rad);
    return { x, y };
  };

  const confidencePath = useMemo(() => {
    if (ciLower >= ciUpper) return "";
    const start = getCoordinates(ciLower);
    const end = getCoordinates(ciUpper);
    const largeArc = ciUpper - ciLower > 50 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  }, [ciLower, ciUpper]);

  // Color mapping based on direction
  const directionColors: Record<string, string> = {
    long: "#10b981", // Emerald
    short: "#ef4444", // Red
    reversal: "#a855f7", // Purple
    breakout: "#3b82f6", // Blue
  };
  const color = directionColors[direction] || "#6b7280";

  // Calculate pointer rotation angle
  const needleRotation = useMemo(() => {
    const percent = probability / 100;
    return startAngle + percent * angleRange;
  }, [probability]);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%", padding: "0.5rem" }}>
      <svg width="200" height="130" viewBox="0 0 200 130" style={{ overflow: "visible" }}>
        {/* Background Arc */}
        <path
          d={`M ${center - radius} ${center} A ${radius} ${radius} 0 0 1 ${center + radius} ${center}`}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />

        {/* Confidence Interval Shaded Arc */}
        {confidencePath && (
          <path
            d={confidencePath}
            fill="none"
            stroke="rgba(255, 255, 255, 0.12)"
            strokeWidth={strokeWidth + 4}
            strokeLinecap="round"
          />
        )}

        {/* Dynamic Colored Value Arc (from 50% to current probability for reference) */}
        {probability > 0 && (
          <path
            d={`M ${getCoordinates(50).x} ${getCoordinates(50).y} A ${radius} ${radius} 0 0 ${probability > 50 ? 1 : 0} ${getCoordinates(probability).x} ${getCoordinates(probability).y}`}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
        )}

        {/* Gauge Needle */}
        <g transform={`translate(${center}, ${center}) rotate(${needleRotation + 90})`}>
          <line
            x1="0"
            y1="0"
            x2="0"
            y2={-radius + 5}
            stroke="#ffffff"
            strokeWidth="3"
            strokeLinecap="round"
            filter="drop-shadow(0 0 4px rgba(0,0,0,0.5))"
          />
          <circle cx="0" cy="0" r="8" fill="#ffffff" />
          <circle cx="0" cy="0" r="4" fill={color} />
        </g>
      </svg>

      {/* Probability details display */}
      <div style={{ textAlign: "center", marginTop: "-10px", zIndex: 10 }}>
        <div style={{ fontSize: "1.75rem", fontFamily: "var(--font-header)", fontWeight: 700, color: "#ffffff" }}>
          {probability.toFixed(1)}%
        </div>
        <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color, letterSpacing: "0.08em", display: "flex", gap: "0.3rem", justifyContent: "center" }}>
          <span>{direction}</span>
          <span style={{ color: "var(--text-muted)" }}>•</span>
          <span style={{ color: "var(--text-secondary)" }}>{strength.replace("_", " ")}</span>
        </div>
        <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
          90% CI: {ciLower.toFixed(1)}% - {ciUpper.toFixed(1)}%
        </div>
      </div>
    </div>
  );
}
