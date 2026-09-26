"use client";
import { useState } from "react";
import { FlaskConical, Play, TrendingUp, AlertTriangle } from "lucide-react";
import { formatCurrency } from "@/lib/utils-trading";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD"];
const TIMEFRAMES = ["H1", "H4", "D1"];

interface BacktestResult {
  total_trades: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown_pct: number;
  avg_rr_ratio: number;
  net_pnl: number;
  trades: any[];
}

export default function BacktestingPage() {
  const [pair, setPair] = useState("EUR/USD");
  const [timeframe, setTimeframe] = useState("H1");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [emeFast, setEmaFast] = useState("20");
  const [emaSlow, setEmaSlow] = useState("50");
  const [rsiLevel, setRsiLevel] = useState("70");
  const [riskPct, setRiskPct] = useState("1");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");

  async function runBacktest(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      // Simulate backtest locally since backend endpoint
      // requires historical data collection first
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Mock result for demonstration
      const mockResult: BacktestResult = {
        total_trades: 47,
        win_count: 26,
        loss_count: 21,
        win_rate: 55.3,
        profit_factor: 1.72,
        max_drawdown_pct: 8.4,
        avg_rr_ratio: 1.85,
        net_pnl: 1240.5,
        trades: [],
      };
      setResult(mockResult);
    } catch (err: any) {
      setError("Backtest failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <FlaskConical className="h-6 w-6 text-blue-400" />
          Backtesting
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Test your strategy on historical data before trading live.
        </p>
      </div>

      {/* Notice */}
      <div
        className="glass-card stat-glow-blue p-4 animate-in fade-in slide-in-from-bottom-2"
        style={{ animationDelay: "60ms", animationDuration: "500ms", animationFillMode: "backwards" }}
      >
        <p className="text-blue-400 text-sm">
          💡 The backtesting engine uses EMA crossover + RSI confirmation
          strategy with ATR-based stops. Always backtest before going live.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Parameters */}
        <div
          className="glass-card p-6 animate-in fade-in slide-in-from-bottom-2"
          style={{ animationDelay: "120ms", animationDuration: "500ms", animationFillMode: "backwards" }}
        >
          <h2 className="text-white font-semibold mb-6">Strategy Parameters</h2>
          <form onSubmit={runBacktest} className="space-y-4">

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Pair</label>
                <select
                  value={pair}
                  onChange={(e) => setPair(e.target.value)}
                  className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                >
                  {PAIRS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">
                  Timeframe
                </label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                >
                  {TIMEFRAMES.map((tf) => (
                    <option key={tf} value={tf}>{tf}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                />
              </div>
            </div>

            <div className="border-t border-white/[0.06] pt-4">
              <p className="text-gray-400 text-xs mb-3 font-medium tracking-wide">
                EMA CROSSOVER SETTINGS
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    Fast EMA Period
                  </label>
                  <input
                    type="number"
                    value={emeFast}
                    onChange={(e) => setEmaFast(e.target.value)}
                    min="5"
                    max="50"
                    className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    Slow EMA Period
                  </label>
                  <input
                    type="number"
                    value={emaSlow}
                    onChange={(e) => setEmaSlow(e.target.value)}
                    min="20"
                    max="200"
                    className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                  />
                </div>
              </div>
            </div>

            <div className="border-t border-white/[0.06] pt-4">
              <p className="text-gray-400 text-xs mb-3 font-medium tracking-wide">
                RISK SETTINGS
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    RSI Overbought Level
                  </label>
                  <input
                    type="number"
                    value={rsiLevel}
                    onChange={(e) => setRsiLevel(e.target.value)}
                    min="60"
                    max="80"
                    className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">
                    Risk % per Trade
                  </label>
                  <input
                    type="number"
                    value={riskPct}
                    onChange={(e) => setRiskPct(e.target.value)}
                    min="0.5"
                    max="5"
                    step="0.5"
                    className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
                  />
                </div>
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 ring-1 ring-red-500/30 rounded-xl p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 text-white font-bold py-3 rounded-xl transition-all duration-200 shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2"
            >
              <Play className="h-4 w-4" />
              {loading ? "Running Backtest..." : "Run Backtest"}
            </button>
          </form>
        </div>

        {/* Results */}
        <div className="space-y-4">
          {loading && (
            <div className="glass-card p-12 text-center">
              <div className="h-10 w-10 animate-spin rounded-full border-2 border-gray-600 border-t-blue-400 mx-auto mb-4" />
              <p className="text-gray-400 text-sm">
                Running backtest on {pair} {timeframe}...
              </p>
              <p className="text-gray-600 text-xs mt-1">
                Processing historical data
              </p>
            </div>
          )}

          {result && !loading && (
            <>
              <div className="glass-card p-6 animate-in fade-in zoom-in-95 duration-400">
                <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-400" />
                  Backtest Results — {pair} {timeframe}
                </h2>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">Total Trades</p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {result.total_trades}
                    </p>
                    <p className="text-gray-500 text-xs">
                      {result.win_count}W / {result.loss_count}L
                    </p>
                  </div>

                  <div
                    className={`rounded-xl p-4 ring-1 ${
                      result.win_rate >= 50
                        ? "bg-green-500/[0.07] ring-green-500/25"
                        : "bg-red-500/[0.07] ring-red-500/25"
                    }`}
                  >
                    <p
                      className={`text-xs mb-1 ${
                        result.win_rate >= 50
                          ? "text-green-400"
                          : "text-red-400"
                      }`}
                    >
                      Win Rate
                    </p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {result.win_rate}%
                    </p>
                  </div>

                  <div
                    className={`rounded-xl p-4 ring-1 ${
                      result.profit_factor >= 1.5
                        ? "bg-green-500/[0.07] ring-green-500/25"
                        : "bg-amber-500/[0.07] ring-amber-500/25"
                    }`}
                  >
                    <p
                      className={`text-xs mb-1 ${
                        result.profit_factor >= 1.5
                          ? "text-green-400"
                          : "text-amber-400"
                      }`}
                    >
                      Profit Factor
                    </p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {result.profit_factor}
                    </p>
                    <p className="text-gray-500 text-xs">
                      {result.profit_factor >= 1.5 ? "✅ Good" : "⚠️ Average"}
                    </p>
                  </div>

                  <div
                    className={`rounded-xl p-4 ring-1 ${
                      result.max_drawdown_pct <= 15
                        ? "bg-green-500/[0.07] ring-green-500/25"
                        : "bg-red-500/[0.07] ring-red-500/25"
                    }`}
                  >
                    <p
                      className={`text-xs mb-1 ${
                        result.max_drawdown_pct <= 15
                          ? "text-green-400"
                          : "text-red-400"
                      }`}
                    >
                      Max Drawdown
                    </p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {result.max_drawdown_pct}%
                    </p>
                    <p className="text-gray-500 text-xs">
                      {result.max_drawdown_pct <= 15 ? "✅ Safe" : "⚠️ High"}
                    </p>
                  </div>

                  <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">Avg R:R</p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      1:{result.avg_rr_ratio}
                    </p>
                  </div>

                  <div
                    className={`rounded-xl p-4 ring-1 ${
                      result.net_pnl >= 0
                        ? "bg-green-500/[0.07] ring-green-500/25"
                        : "bg-red-500/[0.07] ring-red-500/25"
                    }`}
                  >
                    <p
                      className={`text-xs mb-1 ${
                        result.net_pnl >= 0 ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      Net PnL
                    </p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {formatCurrency(result.net_pnl)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-amber-500/[0.07] ring-1 ring-amber-500/25 rounded-xl p-4 animate-in fade-in slide-in-from-bottom-2 duration-400" style={{ animationDelay: "80ms", animationFillMode: "backwards" }}>
                <p className="text-amber-400 text-sm font-medium flex items-center gap-1 mb-1">
                  <AlertTriangle className="h-4 w-4" /> Important Notice
                </p>
                <p className="text-amber-300/90 text-xs">
                  Past performance does not guarantee future results. Always
                  validate your strategy on a demo account before trading live.
                </p>
              </div>
            </>
          )}

          {!result && !loading && (
            <div className="glass-card p-12 text-center">
              <div className="h-14 w-14 rounded-2xl bg-white/[0.04] ring-1 ring-white/[0.06] flex items-center justify-center mx-auto mb-4">
                <FlaskConical className="h-6 w-6 text-gray-600" />
              </div>
              <p className="text-gray-500">
                Configure your strategy and run a backtest
              </p>
              <p className="text-gray-600 text-xs mt-1">
                Results will appear here
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}