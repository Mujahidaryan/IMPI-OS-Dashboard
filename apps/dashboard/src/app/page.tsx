"use client";

import { useState } from "react";
import { useSignals } from "../hooks/useSignals";
import { useWebSocket } from "../hooks/useWebSocket";

// Import Panels
import PriceChart from "../components/PriceChart";
import ProbabilityGauge from "../components/ProbabilityGauge";
import RegimePanel from "../components/RegimePanel";
import GoldArbitragePanel from "../components/GoldArbitragePanel";
import ManipulationPanel from "../components/ManipulationPanel";
import StrategyBreakdown from "../components/StrategyBreakdown";
import RiskPanel from "../components/RiskPanel";
import CorrelationMatrix from "../components/CorrelationMatrix";
import MacroPanel from "../components/MacroPanel";
import AIReasoningPanel from "../components/AIReasoningPanel";
import HealthPanel from "../components/HealthPanel";
import CalibrationChart from "../components/CalibrationChart";

export default function DashboardPage() {
  const {
    signals,
    ticks,
    anomalies,
    regimes,
    risk,
    health,
    calibrationData,
    history,
    loading,
    handleWSMessage,
  } = useSignals();

  // Connect to WebSocket using custom hook
  useWebSocket("ws://localhost:8000/ws", {
    onMessage: handleWSMessage,
  });

  const [focusSymbol, setFocusSymbol] = useState<string>("XAUUSD_EXNESS");

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", minHeight: "60vh", gap: "1rem" }}>
        <div style={{ width: "30px", height: "30px", border: "2px solid rgba(255,255,255,0.05)", borderTopColor: "var(--accent-color)", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", letterSpacing: "0.05em" }}>WARMING UP FUSION ENGINES...</span>
        <style jsx global>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  const focusSignal = signals[focusSymbol];
  const focusTick = ticks[focusSymbol];
  const focusRegime = regimes[focusSymbol] || (focusSignal ? {
    label: focusSignal.regime,
    confidence: 0.85,
    transition_matrix: [[0.33, 0.33, 0.34], [0.33, 0.33, 0.34], [0.33, 0.33, 0.34]],
    persistence_probability: 0.85,
    bars_in_current_regime: 15,
    structural_break: false
  } : undefined);

  const formatPrice = (symbol: string, val: number) => {
    return val.toLocaleString(undefined, {
      minimumFractionDigits: symbol.startsWith("BTC") ? 1 : 2,
      maximumFractionDigits: symbol.startsWith("BTC") ? 1 : 2,
    });
  };

  // Symbols to display in the top selector
  const symbols = [
    { key: "XAUUSD_EXNESS", name: "GOLD Spot CFD", feed: "Exness CFD" },
    { key: "XAUUSDT", name: "GOLD Futures", feed: "Binance Futures" },
    { key: "BTCUSDT", name: "BITCOIN Futures", feed: "Binance Futures" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      
      {/* 1. Top Row: 3 Asset Ticker Grid Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1.25rem" }}>
        {symbols.map((sym) => {
          const tick = ticks[sym.key];
          const signal = signals[sym.key];
          const isActive = focusSymbol === sym.key;
          
          const dirColors: Record<string, string> = {
            long: "var(--success)",
            short: "var(--error)",
            reversal: "#a855f7",
            breakout: "#3b82f6",
          };
          const directionColor = signal ? (dirColors[signal.direction] || "var(--text-secondary)") : "var(--text-secondary)";

          return (
            <div
              key={sym.key}
              onClick={() => setFocusSymbol(sym.key)}
              className="glass-panel"
              style={{
                cursor: "pointer",
                border: isActive ? "1px solid var(--accent-color)" : "1px solid var(--border-color)",
                boxShadow: isActive ? "0 0 15px rgba(99, 102, 241, 0.12)" : "none",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "1rem 1.25rem"
              }}
            >
              <div>
                <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", fontWeight: 600, display: "block" }}>{sym.feed}</span>
                <span style={{ fontSize: "1.05rem", fontFamily: "var(--font-header)", fontWeight: 700, color: "#ffffff" }}>{sym.name}</span>
                <span style={{ fontSize: "1.2rem", fontFamily: "var(--font-header)", fontWeight: 700, display: "block", marginTop: "0.25rem", color: sym.key.startsWith("BTC") ? "#f59e0b" : "#fbbf24" }}>
                  {tick ? `$${formatPrice(sym.key, tick.last)}` : "Warming up..."}
                </span>
              </div>
              <div style={{ textAlign: "right" }}>
                {signal ? (
                  <>
                    <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", display: "block" }}>FUSED DIRECTION</span>
                    <span style={{ fontSize: "1rem", fontWeight: 700, textTransform: "uppercase", color: directionColor, display: "block" }}>
                      {signal.direction}
                    </span>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 600 }}>
                      {signal.probability.toFixed(0)}% Conf
                    </span>
                  </>
                ) : (
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontStyle: "italic" }}>Awaiting signal...</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 2. Main Body Grid */}
      <div className="dashboard-grid">
        
        {/* Left Column: Global context variables (Drawdowns, Covariance matrices, calibration charts, connection latencies) */}
        <div className="col-4" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          
          <div className="glass-panel">
            <h3 className="panel-title">🛡️ PORTFOLIO RISK SAFEGUARD</h3>
            <RiskPanel riskData={risk} />
          </div>

          <div className="glass-panel">
            <h3 className="panel-title">🌎 MACRO ECONOMIC DRIVERS</h3>
            <MacroPanel macroContext={risk?.calibration ? { ...risk.calibration, ...focusSignal?.macro_context?.macro } : undefined} />
          </div>

          <div className="glass-panel">
            <h3 className="panel-title">📊 ROLLING COVARIANCE MATRIX</h3>
            <CorrelationMatrix exposure={risk?.correlation_exposure} />
          </div>

          <div className="glass-panel">
            <h3 className="panel-title">📈 FUSION CALIBRATION STATUS</h3>
            <CalibrationChart calibrationData={calibrationData} metrics={risk?.calibration} />
          </div>

          <div className="glass-panel">
            <h3 className="panel-title">⚙️ SYSTEM DEPENDENCY HEALTH</h3>
            <HealthPanel healthData={health} />
          </div>

        </div>

        {/* Right Column: Focus Asset Details (Price chart, probability gauges, HMM, manipulations) */}
        <div className="col-8" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          
          <div className="glass-panel">
            <h3 className="panel-title" style={{ justifyContent: "space-between" }}>
              <span>📉 REAL-TIME TICK FEED — {focusSymbol.replace("_EXNESS", "")}</span>
              <span style={{ fontSize: "0.75rem", background: "rgba(255,255,255,0.02)", padding: "0.2rem 0.5rem", borderRadius: "4px", border: "1px solid var(--border-color)" }}>
                Timeframe: 1M Ticks
              </span>
            </h3>
            <PriceChart symbol={focusSymbol} latestTick={focusTick} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1.25rem" }}>
            
            {/* Probability Gauge */}
            <div className="glass-panel" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <h3 className="panel-title">🔮 BAYESIAN FUSION POSTERIOR</h3>
              <ProbabilityGauge
                probability={focusSignal ? focusSignal.probability : 50.0}
                ciLower={focusSignal ? focusSignal.ci_lower : 45.0}
                ciUpper={focusSignal ? focusSignal.ci_upper : 55.0}
                direction={focusSignal ? focusSignal.direction : "long"}
                strength={focusSignal ? focusSignal.signal_strength : "insufficient"}
              />
            </div>

            {/* HMM Regime */}
            <div className="glass-panel">
              <h3 className="panel-title">🤖 HMM REGIME DETECTOR</h3>
              <RegimePanel regimeInfo={focusRegime} />
            </div>

          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: "1.25rem" }}>
            
            {/* Gold arbitrage divergence (Gold pairs only) or Crypto manipulation */}
            <div className="glass-panel">
              <h3 className="panel-title">⚠️ LIQUIDITY MANIPULATION</h3>
              {focusSymbol.startsWith("XAU") ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                  <ManipulationPanel score={focusSignal?.manipulation_probability} symbol={focusSymbol} />
                  <div style={{ borderTop: "1px solid rgba(255,255,255,0.03)", paddingTop: "0.6rem" }}>
                    <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)", display: "block", marginBottom: "0.3rem" }}>GOLD CFD vs FUTURES SPREAD</span>
                    <GoldArbitragePanel 
                      exnessTick={focusSymbol === "XAUUSD_EXNESS" ? focusTick : ticks["XAUUSD_EXNESS"]} 
                      binanceTick={focusSymbol === "XAUUSDT" ? focusTick : ticks["XAUUSDT"]}
                      divergence={focusSignal?.gold_arb_divergence}
                    />
                  </div>
                </div>
              ) : (
                <ManipulationPanel score={focusSignal?.manipulation_probability} symbol={focusSymbol} />
              )}
            </div>

            {/* Strategy logit contributions */}
            <div className="glass-panel">
              <h3 className="panel-title">⚡ STRATEGY CONTRIBUTIONS (LOGITS)</h3>
              <StrategyBreakdown contributions={focusSignal?.strategy_contributions} />
            </div>

          </div>

          {/* AI natural language driver breakdown */}
          <div className="glass-panel">
            <h3 className="panel-title">💡 FUSION EXPLANATION BLOCK</h3>
            <AIReasoningPanel 
              reasoning={focusSignal ? focusSignal.reasoning : "Awaiting next closed candle to update AI reasoning vectors..."} 
              expectedMove={focusSignal?.expected_move_pct}
            />
          </div>

        </div>

      </div>

      {/* 3. Bottom Row: Microstructure anomalies scrolling log ticker */}
      <div className="glass-panel" style={{ padding: "0.75rem 1.25rem" }}>
        <h3 className="panel-title" style={{ fontSize: "0.8rem", marginBottom: "0.5rem", borderBottom: "none", paddingBottom: 0 }}>
          🚨 REAL-TIME MICROSTRUCTURE & COMPLIANCE ANOMALY LOGS
        </h3>
        <div style={{ 
          height: "85px", 
          overflowY: "auto", 
          fontFamily: "monospace", 
          fontSize: "0.7rem", 
          color: "var(--text-secondary)", 
          display: "flex", 
          flexDirection: "column", 
          gap: "4px" 
        }}>
          {anomalies.length > 0 ? (
            anomalies.map((anom, idx) => (
              <div 
                key={idx} 
                style={{ 
                  padding: "0.25rem 0.5rem", 
                  background: `rgba(239, 68, 68, ${anom.severity * 0.1})`, 
                  borderLeft: `3px solid var(--error)`, 
                  borderRadius: "2px",
                  display: "flex",
                  justifyContent: "space-between"
                }}
              >
                <span>[{new Date(anom.timestamp_ms).toLocaleTimeString()}] {anom.description}</span>
                <span style={{ color: "var(--error)", fontWeight: 700 }}>SEVERITY: {anom.severity.toFixed(2)}</span>
              </div>
            ))
          ) : (
            <div style={{ color: "var(--text-muted)", fontStyle: "italic", padding: "0.25rem 0" }}>
              No system anomalies detected. Feeds compliance green.
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
