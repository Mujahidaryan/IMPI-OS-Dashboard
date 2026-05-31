import { useState, useEffect, useCallback } from "react";

export interface SignalData {
  asset: string;
  direction: string;
  probability: number;
  ci_lower: number;
  ci_upper: number;
  signal_strength: string;
  manipulation_probability: number;
  regime: string;
  volatility_state: string;
  expected_move_pct: number;
  reliability_rating: number;
  strategy_contributions: Record<string, number>;
  macro_context: Record<string, any>;
  gold_arb_divergence: number;
  reasoning: string;
  timestamp?: number;
}

export interface TickData {
  symbol: string;
  exchange: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  timestamp_ms: number;
}

export interface AnomalyData {
  symbol: string;
  anomaly_type: string;
  severity: number;
  description: string;
  raw_value: number;
  expected_range: [number, number];
  timestamp_ms: number;
}

export function useSignals() {
  const [signals, setSignals] = useState<Record<string, SignalData>>({});
  const [ticks, setTicks] = useState<Record<string, TickData>>({});
  const [anomalies, setAnomalies] = useState<AnomalyData[]>([]);
  const [regimes, setRegimes] = useState<Record<string, any>>({});
  const [risk, setRisk] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [calibrationData, setCalibrationData] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchInitialData = useCallback(async () => {
    try {
      const [signalsRes, riskRes, healthRes, historyRes, calRes] = await Promise.all([
        fetch("/api/signals").then(r => r.ok ? r.json() : null),
        fetch("/api/risk").then(r => r.ok ? r.json() : null),
        fetch("/api/health").then(r => r.ok ? r.json() : null),
        fetch("/api/history?limit=30").then(r => r.ok ? r.json() : null),
        fetch("/api/history/calibration").then(r => r.ok ? r.json() : null),
      ]);

      if (signalsRes && signalsRes.signals) {
        const sigs: Record<string, SignalData> = {};
        signalsRes.signals.forEach((s: any) => {
          if (s.status !== "warming_up") {
            sigs[s.asset] = s;
          }
        });
        setSignals(sigs);
      }
      if (riskRes) setRisk(riskRes);
      if (healthRes) setHealth(healthRes);
      if (historyRes && historyRes.predictions) setHistory(historyRes.predictions);
      if (calRes) setCalibrationData(calRes);
    } catch (err) {
      console.error("[Signals] Failed to fetch initial data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitialData();
    // Poll slower-moving stats like risk & calibration metrics every 15s
    const interval = setInterval(() => {
      fetch("/api/risk").then(r => r.ok ? r.json() : null).then(data => {
        if (data) setRisk(data);
      }).catch(err => console.error(err));
      
      fetch("/api/health").then(r => r.ok ? r.json() : null).then(data => {
        if (data) setHealth(data);
      }).catch(err => console.error(err));
    }, 15000);

    return () => clearInterval(interval);
  }, [fetchInitialData]);

  const handleWSMessage = useCallback((type: string, data: any) => {
    if (type === "prediction") {
      setSignals(prev => ({
        ...prev,
        [data.asset]: data
      }));
      setHistory(prev => [data, ...prev].slice(0, 30));
    } else if (type === "tick") {
      setTicks(prev => ({
        ...prev,
        [data.symbol]: data
      }));
    } else if (type === "anomaly") {
      setAnomalies(prev => [data, ...prev].slice(0, 50));
    } else if (type === "regime") {
      setRegimes(prev => ({
        ...prev,
        [data.symbol]: data.data
      }));
    } else if (type === "health") {
      setHealth(data);
    }
  }, []);

  return {
    signals,
    ticks,
    anomalies,
    regimes,
    risk,
    health,
    calibrationData,
    history,
    loading,
    refresh: fetchInitialData,
    handleWSMessage
  };
}
export type UseSignalsType = ReturnType<typeof useSignals>;
