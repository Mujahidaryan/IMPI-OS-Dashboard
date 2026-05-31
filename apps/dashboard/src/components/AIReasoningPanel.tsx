"use client";

interface AIReasoningPanelProps {
  reasoning?: string;
  expectedMove?: number;
}

export default function AIReasoningPanel({ reasoning, expectedMove = 0 }: AIReasoningPanelProps) {
  if (!reasoning) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "1rem", textAlign: "center" }}>
        No explanation block compiled yet.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {/* Expected move banner */}
      <div style={{
        background: "var(--accent-glow)",
        border: "1px solid rgba(99, 102, 241, 0.2)",
        borderRadius: "6px",
        padding: "0.5rem 0.75rem",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }}>
        <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)", fontWeight: 600 }}>EXPECTED MOVE PCT</span>
        <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--accent-color)" }}>
          ±{expectedMove.toFixed(3)}%
        </span>
      </div>

      <div style={{
        background: "rgba(255,255,255,0.01)",
        border: "1px solid var(--border-color)",
        borderRadius: "8px",
        padding: "0.85rem",
        fontSize: "0.8rem",
        lineHeight: 1.45,
        color: "var(--text-primary)"
      }}>
        {reasoning}
      </div>
    </div>
  );
}
