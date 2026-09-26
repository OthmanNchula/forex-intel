"use client";
import { useState } from "react";
import { riskApi } from "@/lib/api";
import { RiskCalculationResult } from "@/types";
import { useStore } from "@/store/useStore";
import { formatCurrency } from "@/lib/utils-trading";
import { Calculator, AlertTriangle, TrendingUp } from "lucide-react";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD", "USD/CHF"];

export default function RiskCalculatorPage() {
  const { user } = useStore();
  const [pair, setPair] = useState("EUR/USD");
  const [balance, setBalance] = useState(user?.account_balance?.toString() || "10000");
  const [riskPct, setRiskPct] = useState(user?.risk_per_trade_pct?.toString() || "1");
  const [entryPrice, setEntryPrice] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [result, setResult] = useState<RiskCalculationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleCalculate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await riskApi.calculate({
        pair,
        account_balance: parseFloat(balance),
        risk_pct: parseFloat(riskPct),
        entry_price: parseFloat(entryPrice),
        stop_loss: parseFloat(stopLoss),
        take_profit: parseFloat(takeProfit),
      });
      setResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Calculation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Calculator className="h-6 w-6 text-green-400" />
          Risk Calculator
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Calculate your position size, lot size, and risk metrics before entering a trade.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input form */}
        <div
          className="glass-card p-6 animate-in fade-in slide-in-from-bottom-2"
          style={{ animationDelay: "60ms", animationDuration: "500ms", animationFillMode: "backwards" }}
        >
          <h2 className="text-white font-semibold mb-6">Trade Parameters</h2>
          <form onSubmit={handleCalculate} className="space-y-4">

            {/* Pair */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Currency Pair
              </label>
              <select
                value={pair}
                onChange={(e) => setPair(e.target.value)}
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 transition-shadow"
              >
                {PAIRS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>

            {/* Balance and Risk */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  Account Balance ($)
                </label>
                <input
                  type="number"
                  value={balance}
                  onChange={(e) => setBalance(e.target.value)}
                  required
                  min="100"
                  step="100"
                  className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 transition-shadow"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  Risk % per Trade
                </label>
                <input
                  type="number"
                  value={riskPct}
                  onChange={(e) => setRiskPct(e.target.value)}
                  required
                  min="0.1"
                  max="10"
                  step="0.1"
                  className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 transition-shadow"
                />
              </div>
            </div>

            {/* Entry */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Entry Price
              </label>
              <input
                type="number"
                value={entryPrice}
                onChange={(e) => setEntryPrice(e.target.value)}
                required
                step="0.00001"
                placeholder="e.g. 1.08500"
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 placeholder-gray-600 transition-shadow"
              />
            </div>

            {/* Stop Loss */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Stop Loss Price
              </label>
              <input
                type="number"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                required
                step="0.00001"
                placeholder="e.g. 1.08300"
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 placeholder-gray-600 transition-shadow"
              />
            </div>

            {/* Take Profit */}
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Take Profit Price
              </label>
              <input
                type="number"
                value={takeProfit}
                onChange={(e) => setTakeProfit(e.target.value)}
                required
                step="0.00001"
                placeholder="e.g. 1.09000"
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 placeholder-gray-600 transition-shadow"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 ring-1 ring-red-500/30 rounded-xl p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-green-600 to-emerald-500 hover:from-green-500 hover:to-emerald-400 disabled:opacity-50 text-white font-bold py-3 rounded-xl transition-all duration-200 shadow-lg shadow-green-600/20 flex items-center justify-center gap-2"
            >
              <Calculator className="h-4 w-4" />
              {loading ? "Calculating..." : "Calculate Risk"}
            </button>
          </form>
        </div>

        {/* Results */}
        <div className="space-y-4">
          {result ? (
            <>
              {/* Main results */}
              <div
                className="glass-card p-6 animate-in fade-in zoom-in-95 duration-400"
              >
                <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-400" />
                  Calculation Results
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">Lot Size</p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {result.lot_size}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">lots</p>
                  </div>
                  <div className="bg-red-500/[0.07] ring-1 ring-red-500/25 rounded-xl p-4">
                    <p className="text-red-400 text-xs mb-1">Max Risk</p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {formatCurrency(result.risk_amount)}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">
                      {result.risk_pct}% of balance
                    </p>
                  </div>
                  <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">SL Distance</p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {result.sl_pips}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">pips</p>
                  </div>
                  <div className="bg-white/[0.04] ring-1 ring-white/[0.06] rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">Pip Value</p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {formatCurrency(result.pip_value)}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">per pip</p>
                  </div>
                  <div className="bg-green-500/[0.07] ring-1 ring-green-500/25 rounded-xl p-4">
                    <p className="text-green-400 text-xs mb-1">
                      Potential Profit
                    </p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      {formatCurrency(result.potential_profit)}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">at take profit</p>
                  </div>
                  <div
                    className={`rounded-xl p-4 ring-1 ${
                      result.rr_ratio >= 1.5
                        ? "bg-green-500/[0.07] ring-green-500/25"
                        : "bg-red-500/[0.07] ring-red-500/25"
                    }`}
                  >
                    <p
                      className={`text-xs mb-1 ${
                        result.rr_ratio >= 1.5
                          ? "text-green-400"
                          : "text-red-400"
                      }`}
                    >
                      Risk:Reward
                    </p>
                    <p className="text-white text-2xl font-bold tabular-nums">
                      1:{result.rr_ratio}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">
                      {result.rr_ratio >= 1.5 ? "✅ Good" : "⚠️ Too low"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Daily exposure */}
              <div className="glass-card p-4 animate-in fade-in slide-in-from-bottom-2 duration-400" style={{ animationDelay: "80ms", animationFillMode: "backwards" }}>
                <h3 className="text-white font-medium mb-3">
                  Daily Risk Exposure
                </h3>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-gray-400">Used today</span>
                  <span className="text-white tabular-nums">
                    {formatCurrency(result.daily_risk_used)} /{" "}
                    {formatCurrency(result.daily_risk_limit)}
                  </span>
                </div>
                <div className="w-full bg-white/[0.06] rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-2 rounded-full transition-all duration-700 ease-out ${
                      result.daily_risk_used / result.daily_risk_limit > 0.8
                        ? "bg-gradient-to-r from-red-500 to-rose-400"
                        : "bg-gradient-to-r from-blue-500 to-purple-500"
                    }`}
                    style={{
                      width: `${Math.min(
                        (result.daily_risk_used / result.daily_risk_limit) * 100,
                        100
                      )}%`,
                    }}
                  />
                </div>
                <p className="text-gray-500 text-xs mt-2">
                  Remaining: {formatCurrency(result.daily_risk_remaining)}
                </p>
              </div>

              {/* Warnings */}
              {result.warnings.length > 0 && (
                <div className="bg-amber-500/[0.07] ring-1 ring-amber-500/25 rounded-xl p-4 animate-in fade-in slide-in-from-bottom-2 duration-400" style={{ animationDelay: "140ms", animationFillMode: "backwards" }}>
                  <p className="text-amber-400 font-medium text-sm mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4" /> Warnings
                  </p>
                  {result.warnings.map((w, i) => (
                    <p key={i} className="text-amber-300/90 text-sm">
                      {w}
                    </p>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="glass-card p-12 text-center">
              <div className="h-14 w-14 rounded-2xl bg-white/[0.04] ring-1 ring-white/[0.06] flex items-center justify-center mx-auto mb-4">
                <Calculator className="h-6 w-6 text-gray-600" />
              </div>
              <p className="text-gray-500">
                Fill in the trade parameters and click Calculate
              </p>
              <p className="text-gray-600 text-xs mt-2">
                Results will appear here
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}