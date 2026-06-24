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
      <div>
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
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
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
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500"
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
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500"
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
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500"
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
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
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
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
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
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white font-bold py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
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
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
                <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-400" />
                  Calculation Results
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-800 rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">Lot Size</p>
                    <p className="text-white text-2xl font-bold">
                      {result.lot_size}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">lots</p>
                  </div>
                  <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                    <p className="text-red-400 text-xs mb-1">Max Risk</p>
                    <p className="text-white text-2xl font-bold">
                      {formatCurrency(result.risk_amount)}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">
                      {result.risk_pct}% of balance
                    </p>
                  </div>
                  <div className="bg-gray-800 rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">SL Distance</p>
                    <p className="text-white text-2xl font-bold">
                      {result.sl_pips}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">pips</p>
                  </div>
                  <div className="bg-gray-800 rounded-xl p-4">
                    <p className="text-gray-400 text-xs mb-1">Pip Value</p>
                    <p className="text-white text-2xl font-bold">
                      {formatCurrency(result.pip_value)}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">per pip</p>
                  </div>
                  <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
                    <p className="text-green-400 text-xs mb-1">
                      Potential Profit
                    </p>
                    <p className="text-white text-2xl font-bold">
                      {formatCurrency(result.potential_profit)}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">at take profit</p>
                  </div>
                  <div
                    className={`rounded-xl p-4 border ${
                      result.rr_ratio >= 1.5
                        ? "bg-green-500/10 border-green-500/30"
                        : "bg-red-500/10 border-red-500/30"
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
                    <p className="text-white text-2xl font-bold">
                      1:{result.rr_ratio}
                    </p>
                    <p className="text-gray-500 text-xs mt-1">
                      {result.rr_ratio >= 1.5 ? "✅ Good" : "⚠️ Too low"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Daily exposure */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <h3 className="text-white font-medium mb-3">
                  Daily Risk Exposure
                </h3>
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-gray-400">Used today</span>
                  <span className="text-white">
                    {formatCurrency(result.daily_risk_used)} /{" "}
                    {formatCurrency(result.daily_risk_limit)}
                  </span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      result.daily_risk_used / result.daily_risk_limit > 0.8
                        ? "bg-red-500"
                        : "bg-blue-500"
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
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
                  <p className="text-yellow-400 font-medium text-sm mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4" /> Warnings
                  </p>
                  {result.warnings.map((w, i) => (
                    <p key={i} className="text-yellow-300 text-sm">
                      {w}
                    </p>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
              <Calculator className="h-12 w-12 text-gray-700 mx-auto mb-4" />
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