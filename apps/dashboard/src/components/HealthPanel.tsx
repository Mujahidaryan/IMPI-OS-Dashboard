"use client";

interface HealthPanelProps {
  healthData?: {
    status: string;
    redis: string;
    postgresql: string;
    feeds: Record<
      string,
      { status: string; last_seen_ms: number; delay_seconds: number }
    >;
  };
}

export default function HealthPanel({ healthData }: HealthPanelProps) {
  if (!healthData) {
    return (
      <div
        style={{
          color: "var(--text-muted)",
          fontSize: "0.85rem",
          padding: "1rem",
          textAlign: "center",
        }}
      >
        Loading engine connection health checklist...
      </div>
    );
  }

  const { status, redis, postgresql, feeds } = healthData;

  const getStatusColor = (val: string) => {
    if (val === "connected" || val === "green" || val === "healthy")
      return "var(--success)";
    if (val === "degraded" || val === "yellow") return "var(--warning)";
    return "var(--error)";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      {/* Core connections list */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "0.5rem",
        }}
      >
        <div
          style={{
            background: "rgba(255,255,255,0.01)",
            border: "1px solid var(--border-color)",
            padding: "0.4rem 0.6rem",
            borderRadius: "6px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)" }}>
            REDIS CACHE
          </span>
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              color: getStatusColor(redis),
              textTransform: "uppercase",
            }}
          >
            {redis}
          </span>
        </div>
        <div
          style={{
            background: "rgba(255,255,255,0.01)",
            border: "1px solid var(--border-color)",
            padding: "0.4rem 0.6rem",
            borderRadius: "6px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)" }}>
            POSTGRESQL
          </span>
          <span
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              color: getStatusColor(postgresql),
              textTransform: "uppercase",
            }}
          >
            {postgresql}
          </span>
        </div>
      </div>

      {/* Feed latencies list */}
      <div>
        <span
          style={{
            fontSize: "0.65rem",
            color: "var(--text-secondary)",
            fontWeight: 600,
            display: "block",
            marginBottom: "0.3rem",
          }}
        >
          FEED LATENCIES / STALENESS MONITOR
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
          {Object.entries(feeds).map(([name, val]) => (
            <div
              key={name}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "0.35rem 0.5rem",
                background: "rgba(255,255,255,0.01)",
                border: "1px solid var(--border-color)",
                borderRadius: "4px",
                fontSize: "0.7rem",
              }}
            >
              <span style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                {name.replace("_", " ")}
              </span>
              <div
                style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}
              >
                <span
                  style={{ color: "var(--text-muted)", fontSize: "0.6rem" }}
                >
                  {typeof val.delay_seconds === "number"
                    ? val.delay_seconds.toFixed(1)
                    : "—"}
                  s
                </span>
                <span
                  style={{
                    fontSize: "0.65rem",
                    fontWeight: 700,
                    color: getStatusColor(val.status),
                    textTransform: "uppercase",
                  }}
                >
                  ● {val.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
