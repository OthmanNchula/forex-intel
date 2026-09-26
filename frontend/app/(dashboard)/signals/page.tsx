"use client";
import { useEffect, useState } from "react";
import { analysisApi } from "@/lib/api";
import { Signal } from "@/types";
import { useStore } from "@/store/useStore";
import {
  getDirectionBg,
  getConfidenceLabel,
  formatPrice,
  formatCurrency,
} from "@/lib/utils-trading";
import { Zap, RefreshCw, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD"];
const TIMEFRAMES = ["M15", "H1", "H4", "D1"];

export default function SignalsPage() {
  const { activePair, setActivePair } = useStore();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [timeframe, setTimeframe] = useState("H1");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadSignals();
  }, []);

  async function loadSignals() {
    setLoading(true);
    try {
      const res = await analysisApi.getSignals();
      setSignals(res.data || []);
    } catch {
      setError("Failed to load signals.");
    } finally {
      setLoading(false);
    }
  }

  async function generateSignal() {
    setGenerating(true);
    setError("");
    try {
      const res = await analysisApi.generateSignal(activePair, timeframe);
      const newSignal = res.data;
      setSignals((prev) => [newSignal, ...prev]);
      setSelectedSignal(newSignal);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Failed to generate signal. Try again."
      );
    } finally {
      setGenerating(false);
    }
  }

  async function dismissSignal(id: string) {
    try {
      await analysisApi.dismissSignal(id);
      setSignals((prev) => prev.filter((s) => s.id !== id));
      if (selectedSignal?.id === id) setSelectedSignal(null);
    } catch {
      console.error("Failed to dismiss signal");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between animate-in fade-in slide-in-from-bottom-2 duration-500">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap className="h-6 w-6 text-yellow-400" />
            AI Signals
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Generate AI-powered trading signals for any pair
          </p>
        </div>
        <button
          onClick={loadSignals}
          className="h-9 w-9 flex items-center justify-center rounded-xl text-gray-400 hover:text-white hover:bg-white/[0.06] transition-all duration-200"
        >
          <RefreshCw className="h-4.5 w-4.5" />
        </button>
      </div>

      {/* Auto Signal Engine Status */}
      <div
        className="glass-card stat-glow-blue p-4 animate-in fade-in slide-in-from-bottom-2"
        style={{ animationDelay: "60ms", animationDuration: "500ms", animationFillMode: "backwards" }}
      >
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-400" />
            </span>
            <span className="text-green-400 text-sm font-medium">Auto Signal Engine Active</span>
          </div>
          <span className="text-gray-400 text-xs">Scanning 6 pairs every 15 minutes</span>
        </div>
        <p className="text-gray-400 text-xs mt-2">
          Signals appear automatically when confidence ≥ 70% and R:R ≥ 1.5 on H1 or H4 timeframes.
          You can also generate signals manually using the form above.
        </p>
      </div>

      {/* Signal Generator */}
      <div
        className="glass-card p-6 animate-in fade-in slide-in-from-bottom-2"
        style={{ animationDelay: "120ms", animationDuration: "500ms", animationFillMode: "backwards" }}
      >
        <h2 className="text-white font-semibold mb-4">Generate New Signal</h2>
        <div className="flex flex-wrap gap-3">
          {/* Pair selector */}
          <select
            value={activePair}
            onChange={(e) => setActivePair(e.target.value)}
            className="bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
          >
            {PAIRS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>

          {/* Timeframe selector */}
          <div className="flex gap-1 bg-white/[0.03] ring-1 ring-white/[0.06] rounded-xl p-1">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  timeframe === tf
                    ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md shadow-blue-600/20"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Generate button */}
          <button
            onClick={generateSignal}
            disabled={generating}
            className="flex items-center gap-2 bg-gradient-to-r from-yellow-500 to-amber-500 hover:from-yellow-400 hover:to-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-bold px-6 py-2.5 rounded-xl transition-all duration-200 shadow-lg shadow-yellow-500/20"
          >
            <Zap className="h-4 w-4" />
            {generating ? "Analyzing..." : "Generate Signal"}
          </button>
        </div>

        {generating && (
          <div className="mt-4 bg-blue-500/10 ring-1 ring-blue-500/25 rounded-xl p-4">
            <p className="text-blue-400 text-sm animate-pulse">
              🤖 AI is analyzing {activePair} on {timeframe}...
              fetching market data, computing indicators, generating signal.
            </p>
          </div>
        )}

        {error && (
          <div className="mt-4 bg-red-500/10 ring-1 ring-red-500/30 rounded-xl p-3">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Signal list */}
        <div className="lg:col-span-1 space-y-3">
          <h2 className="text-white font-semibold">Active Signals</h2>
          {loading ? (
            <LoadingSpinner size="sm" />
          ) : signals.length === 0 ? (
            <div className="glass-card p-6 text-center">
              <p className="text-gray-500 text-sm">No signals yet.</p>
              <p className="text-gray-600 text-xs mt-1">
                Generate your first signal above.
              </p>
            </div>
          ) : (
            signals.map((signal, i) => {
              const conf = getConfidenceLabel(signal.confidence_score || 0);
              const isSelected = selectedSignal?.id === signal.id;
              return (
                <button
                  key={signal.id}
                  onClick={() => setSelectedSignal(signal)}
                  className={`w-full text-left rounded-xl p-4 transition-all duration-200 animate-in fade-in slide-in-from-left-2 ${
                    isSelected
                      ? "bg-gradient-to-r from-blue-600/15 to-purple-600/10 ring-1 ring-blue-500/40 shadow-[0_0_20px_-8px_rgba(59,130,246,0.6)]"
                      : "bg-white/[0.03] ring-1 ring-white/[0.05] hover:ring-white/[0.1] hover:bg-white/[0.05]"
                  }`}
                  style={{ animationDelay: `${i * 40}ms`, animationDuration: "400ms", animationFillMode: "backwards" }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-semibold">{signal.pair}</span>
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-md border ${getDirectionBg(signal.direction)}`}
                    >
                      {signal.direction}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-xs">{signal.timeframe}</span>
                    <span className={`text-xs font-medium ${conf.color}`}>
                      {signal.confidence_score}% confidence
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Signal detail */}
        <div className="lg:col-span-2">
          {selectedSignal ? (
            <SignalDetail
              signal={selectedSignal}
              onDismiss={() => dismissSignal(selectedSignal.id)}
            />
          ) : (
            <div className="glass-card p-12 text-center">
              <div className="h-14 w-14 rounded-2xl bg-white/[0.04] ring-1 ring-white/[0.06] flex items-center justify-center mx-auto mb-4">
                <Zap className="h-6 w-6 text-gray-600" />
              </div>
              <p className="text-gray-500">
                Select a signal or generate a new one to see details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SignalDetail({
  signal,
  onDismiss,
}: {
  signal: Signal;
  onDismiss: () => void;
}) {
  const conf = getConfidenceLabel(signal.confidence_score || 0);

  return (
    <div className="glass-card p-6 space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-400">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-white text-xl font-bold">{signal.pair}</span>
          <span
            className={`font-bold px-3 py-1 rounded-lg border text-sm ${getDirectionBg(signal.direction)}`}
          >
            {signal.direction === "BUY" ? (
              <span className="flex items-center gap-1">
                <TrendingUp className="h-4 w-4" /> BUY
              </span>
            ) : signal.direction === "SELL" ? (
              <span className="flex items-center gap-1">
                <TrendingDown className="h-4 w-4" /> SELL
              </span>
            ) : (
              "NO TRADE"
            )}
          </span>
          <span className="text-gray-400 text-sm">{signal.timeframe}</span>
        </div>
        <button
          onClick={onDismiss}
          className="text-gray-500 hover:text-red-400 text-xs ring-1 ring-white/[0.08] hover:ring-red-400/40 px-3 py-1.5 rounded-lg transition-all duration-200"
        >
          Dismiss
        </button>
      </div>

      {/* Confidence */}
      <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-gray-400 text-sm">AI Confidence</span>
          <span className={`font-bold ${conf.color}`}>
            {signal.confidence_score}% — {conf.label}
          </span>
        </div>
        <div className="w-full bg-white/[0.06] rounded-full h-2 overflow-hidden">
          <div
            className={`h-2 rounded-full transition-all duration-700 ease-out ${
              (signal.confidence_score || 0) >= 70
                ? "bg-gradient-to-r from-green-500 to-emerald-400"
                : (signal.confidence_score || 0) >= 50
                ? "bg-gradient-to-r from-yellow-500 to-amber-400"
                : "bg-gradient-to-r from-red-500 to-rose-400"
            }`}
            style={{ width: `${signal.confidence_score || 0}%` }}
          />
        </div>
      </div>

      {/* Price levels */}
      {signal.direction !== "NO_TRADE" && (
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-blue-500/[0.07] ring-1 ring-blue-500/25 rounded-xl p-4">
            <p className="text-blue-400 text-xs mb-1">Entry Zone</p>
            <p className="text-white font-mono text-sm tabular-nums">
              {formatPrice(signal.entry_low || 0, signal.pair)} —{" "}
              {formatPrice(signal.entry_high || 0, signal.pair)}
            </p>
          </div>
          <div className="bg-red-500/[0.07] ring-1 ring-red-500/25 rounded-xl p-4">
            <p className="text-red-400 text-xs mb-1">Stop Loss</p>
            <p className="text-white font-mono text-sm tabular-nums">
              {formatPrice(signal.stop_loss || 0, signal.pair)}
            </p>
          </div>
          <div className="bg-green-500/[0.07] ring-1 ring-green-500/25 rounded-xl p-4">
            <p className="text-green-400 text-xs mb-1">Take Profit 1</p>
            <p className="text-white font-mono text-sm tabular-nums">
              {formatPrice(signal.take_profit_1 || 0, signal.pair)}
            </p>
          </div>
          <div className="bg-green-500/[0.07] ring-1 ring-green-500/25 rounded-xl p-4">
            <p className="text-green-400 text-xs mb-1">Take Profit 2</p>
            <p className="text-white font-mono text-sm tabular-nums">
              {formatPrice(signal.take_profit_2 || 0, signal.pair)}
            </p>
          </div>
          <div className="bg-green-500/[0.07] ring-1 ring-green-500/25 rounded-xl p-4">
            <p className="text-green-400 text-xs mb-1">Take Profit 3</p>
            <p className="text-white font-mono text-sm tabular-nums">
              {formatPrice(signal.take_profit_3 || 0, signal.pair)}
            </p>
          </div>
          <div className="bg-white/[0.04] ring-1 ring-white/[0.08] rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Risk:Reward</p>
            <p className="text-white font-bold text-lg tabular-nums">
              1:{signal.rr_ratio?.toFixed(1)}
            </p>
          </div>
        </div>
      )}

      {/* Indicators */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "RSI", value: signal.rsi?.toFixed(1) },
          { label: "EMA20", value: formatPrice(signal.ema20 || 0, signal.pair) },
          { label: "EMA50", value: formatPrice(signal.ema50 || 0, signal.pair) },
          { label: "MACD", value: signal.macd_hist?.toFixed(5) },
          { label: "ATR", value: signal.atr?.toFixed(5) },
          { label: "Price", value: formatPrice(signal.current_price, signal.pair) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white/[0.03] ring-1 ring-white/[0.06] rounded-lg p-3">
            <p className="text-gray-500 text-xs mb-1">{label}</p>
            <p className="text-white font-mono text-xs tabular-nums">{value || "—"}</p>
          </div>
        ))}
      </div>

      {/* AI Explanation */}
      {signal.ai_explanation && (
        <div className="bg-blue-500/[0.07] ring-1 ring-blue-500/20 rounded-xl p-4">
          <p className="text-blue-400 text-xs font-semibold mb-2">
            🤖 AI Analysis
          </p>
          <p className="text-gray-300 text-sm leading-relaxed">
            {signal.ai_explanation}
          </p>
        </div>
      )}

      {/* Risk Warning */}
      {signal.risk_warning && (
        <div className="bg-amber-500/[0.07] ring-1 ring-amber-500/25 rounded-xl p-4">
          <p className="text-amber-400 text-xs font-semibold mb-2 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" /> Risk Warning
          </p>
          <p className="text-amber-300/90 text-sm">{signal.risk_warning}</p>
        </div>
      )}
    </div>
  );
}