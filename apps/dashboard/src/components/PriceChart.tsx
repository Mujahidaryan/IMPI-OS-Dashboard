"use client";

import { useEffect, useRef } from "react";
import { createChart, IChartApi, ISeriesApi } from "lightweight-charts";
import { TickData } from "../hooks/useSignals";

interface PriceChartProps {
  symbol: string;
  latestTick?: TickData;
}

export default function PriceChart({ symbol, latestTick }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create TradingView Chart
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 220,
      layout: {
        background: { color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.03)" },
        horzLines: { color: "rgba(255,255,255,0.03)" },
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.06)",
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.06)",
        timeVisible: true,
        secondsVisible: false,
      },
      handleScale: false,
      handleScroll: false,
    });

    // Create an Area Series for high performance real-time ticks
    const areaSeries = chart.addAreaSeries({
      lineColor: symbol.startsWith("BTC") ? "#f59e0b" : "#fbbf24",
      topColor: symbol.startsWith("BTC") ? "rgba(245, 158, 11, 0.2)" : "rgba(251, 191, 36, 0.2)",
      bottomColor: "rgba(7, 9, 14, 0)",
      lineWidth: 2,
      priceFormat: {
        type: "price",
        precision: symbol.startsWith("BTC") ? 1 : 2,
        minMove: symbol.startsWith("BTC") ? 0.1 : 0.01,
      },
    });

    chartRef.current = chart;
    seriesRef.current = areaSeries;

    // Handle resizing
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [symbol]);

  // Update chart data with incoming real-time ticks
  useEffect(() => {
    if (!seriesRef.current || !latestTick) return;

    const timestampSec = Math.floor(latestTick.timestamp_ms / 1000);
    
    // Add point to series
    try {
      seriesRef.current.update({
        time: timestampSec as any,
        value: latestTick.last,
      });
    } catch (e) {
      // Ignore timestamp sequencing errors in dev mode restarts
    }
  }, [latestTick]);

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <div 
        ref={containerRef} 
        style={{ width: "100%", height: "220px", borderRadius: "8px", overflow: "hidden" }} 
      />
    </div>
  );
}
