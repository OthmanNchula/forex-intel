"use client";
import { useEffect, useState, useRef } from "react";
import { marketApi, analysisApi } from "@/lib/api";
import { useStore } from "@/store/useStore";
import { Indicators, Signal } from "@/types";
import {
  formatPrice,
  getTrendColor,
  getRSILabel,
  getDirectionBg,
} from "@/lib/utils-trading";
import { RefreshCw, Zap, TrendingUp } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD"];
const TIMEFRAMES = ["M15", "H1", "H4", "D1"];

export default function MarketPage() {
  const { activePair, setActivePair, activeTimeframe, setActiveTimeframe } = useStore();
  const [indicators, setIndicators] = useState<Indicators | null>(null);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    loadMarketData();
  }, [activePair, activeTimeframe]);

  useEffect(() => {
    if (indicators?.chart_data) {
      initChart(indicators.chart_data);
    }
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [indicators]);

  async function loadMarketData() {
    setLoading(true);
    try {
      const [indRes, signalRes] = await Promise.allSettled([
        marketApi.getIndicators(activePair, activeTimeframe),
        analysisApi.getLatestSignal(activePair),
      ]);
      if (indRes.status === "fulfilled") {
        setIndicators(indRes.value.data.indicators);
      }
      if (signalRes.status === "fulfilled") {
        setSignal(signalRes.value.data);
      } else {
        setSignal(null);
      }
    } catch (err) {
      console.error("Market data error:", err);
    } finally {
      setLoading(false);
    }
  }

  async function generateSignal() {
    setGenerating(true);
    try {
      const res = await analysisApi.generateSignal(activePair, activeTimeframe);
      setSignal(res.data);
    } catch (err) {
      console.error("Signal generation error:", err);
    } finally {
      setGenerating(false);
    }
  }

  async function initChart(chartData: any[]) {
    if (!chartContainerRef.current || !chartData.length) return;

    const {
      createChart,
      ColorType,
      CrosshairMode,
      CandlestickSeries,
      LineSeries,
    } = await import("lightweight-charts");

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0b0f19" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#374151" },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: 450,
    });

    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    candleSeries.setData(
      chartData.map((d) => ({
        time: d.time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }))
    );

    const ema20Series = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 1,
      title: "EMA20",
    });
    ema20Series.setData(
      chartData.map((d) => ({ time: d.time, value: d.ema20 }))
    );

    const ema50Series = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      title: "EMA50",
    });
    ema50Series.setData(
      chartData.map((d) => ({ time: d.time, value: d.ema50 }))
    );

    if (signal && signal.direction !== "NO_TRADE") {
      if (signal.stop_loss) {
        const slSeries = chart.addSeries(LineSeries, {
          color: "#ef4444",
          lineWidth: 1,
          lineStyle: 2,
          title: "SL",
        });
        slSeries.setData(
          chartData.map((d) => ({ time: d.time, value: signal.stop_loss! }))
        );
      }
      if (signal.take_profit_1) {
        const tpSeries = chart.addSeries(LineSeries, {
          color: "#10b981",
          lineWidth: 1,
          lineStyle: 2,
          title: "TP1",
        });
        tpSeries.setData(
          chartData.map((d) => ({ time: d.time, value: signal.take_profit_1! }))
        );
      }
    }

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    });
    if (chartContainerRef.current) {
      resizeObserver.observe(chartContainerRef.current);
    }
  }

  const rsiLabel = indicators ? getRSILabel(indicators.rsi) : null;

  return (
    <div className="space-y-4 pt-2">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 animate-in fade-in slide-in-from-bottom-2 duration-500">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <TrendingUp className="h-6 w-6 text-blue-400" />
          Market Chart
        </h1>
        <button
          onClick={loadMarketData}
          className="h-9 w-9 flex items-center justify-center rounded-xl text-gray-400 hover:text-white hover:bg-white/[0.06] transition-all duration-200"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Controls */}
      <div
        className="flex flex-wrap gap-3 animate-in fade-in slide-in-from-bottom-2"
        style={{ animationDelay: "60ms", animationDuration: "500ms", animationFillMode: "backwards" }}
      >
        <select
          value={activePair}
          onChange={(e) => setActivePair(e.target.value)}
          className="bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
        >
          {PAIRS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>

        <div className="flex gap-1 bg-white/[0.03] ring-1 ring-white/[0.06] rounded-xl p-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setActiveTimeframe(tf)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                activeTimeframe === tf
                  ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md shadow-blue-600/20"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>

        <button
          onClick={generateSignal}
          disabled={generating}
          className="flex items-center gap-2 bg-gradient-to-r from-yellow-500 to-amber-500 hover:from-yellow-400 hover:to-amber-400 disabled:opacity-50 text-black font-bold px-4 py-2 rounded-xl transition-all duration-200 shadow-lg shadow-yellow-500/20 text-sm"
        >
          <Zap className="h-4 w-4" />
          {generating ? "Analyzing..." : "Get AI Signal"}
        </button>
      </div>

      {/* Chart */}
      <div
        className="glass-card overflow-hidden animate-in fade-in slide-in-from-bottom-2"
        style={{ animationDelay: "120ms", animationDuration: "500ms", animationFillMode: "backwards" }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06] flex-wrap gap-2">
          <div className="flex items-center gap-4">
            <span className="text-white font-bold">{activePair}</span>
            <span className="text-gray-400 text-sm">{activeTimeframe}</span>
            {indicators && (
              <span className="text-white font-mono text-sm tabular-nums">
                {formatPrice(indicators.current_price, activePair)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 rounded-full bg-blue-400 inline-block" />
              EMA20
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 rounded-full bg-yellow-400 inline-block" />
              EMA50
            </span>
            {signal && signal.direction !== "NO_TRADE" && (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 rounded-full bg-red-400 inline-block" />
                  SL
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 rounded-full bg-green-400 inline-block" />
                  TP1
                </span>
              </>
            )}
          </div>
        </div>
        {loading ? (
          <div className="h-96 flex items-center justify-center">
            <LoadingSpinner />
          </div>
        ) : (
          <div ref={chartContainerRef} className="w-full" />
        )}
      </div>

      {/* Indicators + Signal row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {indicators && (
          <div
            className="glass-card p-4 animate-in fade-in slide-in-from-bottom-2"
            style={{ animationDelay: "180ms", animationDuration: "500ms", animationFillMode: "backwards" }}
          >
            <h2 className="text-white font-semibold mb-4">
              Technical Indicators
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-3">
                <p className="text-gray-400 text-xs mb-1">Trend</p>
                <p className={`font-bold ${getTrendColor(indicators.trend)}`}>
                  {indicators.trend}
                </p>
              </div>
              <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-3">
                <p className="text-gray-400 text-xs mb-1">Volatility</p>
                <p className="text-white font-bold">{indicators.volatility}</p>
              </div>
              <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-3">
                <p className="text-gray-400 text-xs mb-1">RSI (14)</p>
                <p className={`font-bold ${rsiLabel?.color}`}>
                  {indicators.rsi.toFixed(1)} — {rsiLabel?.label}
                </p>
              </div>
              <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-3">
                <p className="text-gray-400 text-xs mb-1">MACD Hist</p>
                <p className={`font-bold font-mono text-sm tabular-nums ${
                  indicators.macd_hist > 0 ? "text-green-400" : "text-red-400"
                }`}>
                  {indicators.macd_hist.toFixed(5)}
                </p>
              </div>
              <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-3">
                <p className="text-gray-400 text-xs mb-1">EMA Cross</p>
                <p className={`font-bold ${
                  indicators.ema_cross === "ABOVE" ? "text-green-400" : "text-red-400"
                }`}>
                  EMA20 {indicators.ema_cross} EMA50
                </p>
              </div>
              <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-3">
                <p className="text-gray-400 text-xs mb-1">ATR (14)</p>
                <p className="text-white font-mono text-sm tabular-nums">
                  {formatPrice(indicators.atr, activePair)}
                </p>
              </div>
              {indicators.nearest_support && (
                <div className="bg-green-500/[0.07] ring-1 ring-green-500/20 rounded-lg p-3">
                  <p className="text-green-400 text-xs mb-1">Support</p>
                  <p className="text-white font-mono text-sm tabular-nums">
                    {formatPrice(indicators.nearest_support, activePair)}
                  </p>
                </div>
              )}
              {indicators.nearest_resistance && (
                <div className="bg-red-500/[0.07] ring-1 ring-red-500/20 rounded-lg p-3">
                  <p className="text-red-400 text-xs mb-1">Resistance</p>
                  <p className="text-white font-mono text-sm tabular-nums">
                    {formatPrice(indicators.nearest_resistance, activePair)}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        <div
          className="glass-card p-4 animate-in fade-in slide-in-from-bottom-2"
          style={{ animationDelay: "240ms", animationDuration: "500ms", animationFillMode: "backwards" }}
        >
          <h2 className="text-white font-semibold mb-4">Latest AI Signal</h2>
          {signal ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className={`font-bold px-3 py-1.5 rounded-lg border text-sm ${getDirectionBg(signal.direction)}`}>
                  {signal.direction}
                </span>
                <span className="text-gray-400 text-sm">
                  Confidence:{" "}
                  <span className="text-white font-bold">
                    {signal.confidence_score}%
                  </span>
                </span>
              </div>
              {signal.direction !== "NO_TRADE" && (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-2">
                    <p className="text-gray-500 text-xs">Entry</p>
                    <p className="text-white font-mono tabular-nums">
                      {formatPrice(signal.entry_low || 0, activePair)}
                    </p>
                  </div>
                  <div className="bg-red-500/[0.07] ring-1 ring-red-500/20 rounded-lg p-2">
                    <p className="text-red-400 text-xs">Stop Loss</p>
                    <p className="text-white font-mono tabular-nums">
                      {formatPrice(signal.stop_loss || 0, activePair)}
                    </p>
                  </div>
                  <div className="bg-green-500/[0.07] ring-1 ring-green-500/20 rounded-lg p-2">
                    <p className="text-green-400 text-xs">TP1</p>
                    <p className="text-white font-mono tabular-nums">
                      {formatPrice(signal.take_profit_1 || 0, activePair)}
                    </p>
                  </div>
                  <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-lg p-2">
                    <p className="text-gray-500 text-xs">R:R</p>
                    <p className="text-white font-bold tabular-nums">
                      1:{signal.rr_ratio?.toFixed(1)}
                    </p>
                  </div>
                </div>
              )}
              {signal.ai_explanation && (
                <div className="bg-blue-500/[0.07] ring-1 ring-blue-500/20 rounded-lg p-3">
                  <p className="text-blue-400 text-xs font-semibold mb-1">
                    🤖 AI Analysis
                  </p>
                  <p className="text-gray-300 text-xs leading-relaxed">
                    {signal.ai_explanation}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500 text-sm">
                No signal for {activePair} yet.
              </p>
              <button
                onClick={generateSignal}
                disabled={generating}
                className="mt-3 text-yellow-400 hover:text-yellow-300 text-sm flex items-center gap-1 mx-auto transition-colors"
              >
                <Zap className="h-3 w-3" />
                {generating ? "Generating..." : "Generate Signal"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}