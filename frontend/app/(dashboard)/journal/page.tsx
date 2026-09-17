"use client";
import { useEffect, useState } from "react";
import { journalApi } from "@/lib/api";
import { Trade, TradeStats } from "@/types";
import {
  formatCurrency,
  formatDate,
  getDirectionBg,
  getResultColor,
  getPnLColor,
} from "@/lib/utils-trading";
import { BookOpen, Plus, X, TrendingUp } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD"];

export default function JournalPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [filterResult, setFilterResult] = useState("");

  useEffect(() => {
    loadJournal();
  }, []);

  async function loadJournal() {
    setLoading(true);
    try {
      const [tradesRes, statsRes] = await Promise.all([
        journalApi.getTrades(),
        journalApi.getStats(),
      ]);
      setTrades(tradesRes.data || []);
      setStats(statsRes.data);
    } catch (err) {
      console.error("Journal load error:", err);
    } finally {
      setLoading(false);
    }
  }

  async function closeTrade(
    id: string,
    result: string,
    pnl: number,
    pnlPips: number
  ) {
    try {
      await journalApi.updateTrade(id, {
        result,
        pnl,
        pnl_pips: pnlPips,
        closed_at: new Date().toISOString(),
      });
      loadJournal();
    } catch (err) {
      console.error("Close trade error:", err);
    }
  }

  async function deleteTrade(id: string) {
    if (!confirm("Delete this trade?")) return;
    try {
      await journalApi.deleteTrade(id);
      setTrades((prev) => prev.filter((t) => t.id !== id));
    } catch (err) {
      console.error("Delete trade error:", err);
    }
  }

  const filtered = filterResult
    ? trades.filter((t) => t.result === filterResult)
    : trades;

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-purple-400" />
            Trade Journal
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Track and review all your trades
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Trade
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Total Trades</p>
            <p className="text-white text-xl font-bold">{stats.total_trades}</p>
            <p className="text-gray-500 text-xs">{stats.open_trades} open</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Win Rate</p>
            <p className="text-green-400 text-xl font-bold">{stats.win_rate}%</p>
            <p className="text-gray-500 text-xs">
              {stats.wins}W / {stats.losses}L
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Total PnL</p>
            <p className={`text-xl font-bold ${getPnLColor(stats.total_pnl)}`}>
              {formatCurrency(stats.total_pnl)}
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-gray-400 text-xs mb-1">Avg R:R</p>
            <p className="text-white text-xl font-bold">{stats.avg_rr}</p>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2">
        {["", "OPEN", "WIN", "LOSS", "BREAKEVEN"].map((f) => (
          <button
            key={f}
            onClick={() => setFilterResult(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filterResult === f
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {f || "All"}
          </button>
        ))}
      </div>

      {/* Trades table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-16">
            <BookOpen className="h-12 w-12 text-gray-700 mx-auto mb-4" />
            <p className="text-gray-500">No trades found.</p>
            <button
              onClick={() => setShowForm(true)}
              className="mt-3 text-purple-400 hover:text-purple-300 text-sm"
            >
              Add your first trade →
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-xs">
                  <th className="text-left px-4 py-3">Pair</th>
                  <th className="text-left px-4 py-3">Direction</th>
                  <th className="text-left px-4 py-3">Entry</th>
                  <th className="text-left px-4 py-3">SL</th>
                  <th className="text-left px-4 py-3">TP</th>
                  <th className="text-left px-4 py-3">Lots</th>
                  <th className="text-left px-4 py-3">Risk</th>
                  <th className="text-left px-4 py-3">Result</th>
                  <th className="text-left px-4 py-3">PnL</th>
                  <th className="text-left px-4 py-3">Date</th>
                  <th className="text-left px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((trade) => (
                  <tr
                    key={trade.id}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                  >
                    <td className="px-4 py-3 text-white font-medium">
                      {trade.pair}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded border ${getDirectionBg(trade.direction)}`}
                      >
                        {trade.direction}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-300 font-mono">
                      {trade.entry_price}
                    </td>
                    <td className="px-4 py-3 text-red-400 font-mono">
                      {trade.stop_loss}
                    </td>
                    <td className="px-4 py-3 text-green-400 font-mono">
                      {trade.take_profit}
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {trade.lot_size}
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {formatCurrency(trade.risk_amount)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded border ${getResultColor(trade.result)}`}
                      >
                        {trade.result}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-mono font-bold ${getPnLColor(trade.pnl || 0)}`}
                      >
                        {trade.pnl !== null
                          ? formatCurrency(trade.pnl)
                          : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatDate(trade.opened_at)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {trade.result === "OPEN" && (
                          <CloseTradeButton
                            trade={trade}
                            onClose={closeTrade}
                          />
                        )}
                        <button
                          onClick={() => deleteTrade(trade.id)}
                          className="text-gray-600 hover:text-red-400 transition-colors"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Trade Modal */}
      {showForm && (
        <AddTradeModal
          onClose={() => setShowForm(false)}
          onAdded={() => {
            setShowForm(false);
            loadJournal();
          }}
        />
      )}
    </div>
  );
}

function CloseTradeButton({
  trade,
  onClose,
}: {
  trade: Trade;
  onClose: (id: string, result: string, pnl: number, pnlPips: number) => void;
}) {
  const [closePrice, setClosePrice] = useState("");
  const [showInput, setShowInput] = useState(false);

function handleClose() {
    const cp = parseFloat(closePrice);
    console.log("Close price:", cp, "Trade:", trade.pair, trade.direction);
    if (!cp || isNaN(cp)) {
      console.error("Invalid close price");
      return;
    }

    // Correct pip size per pair
    let pipSize = 0.0001;
    if (trade.pair.includes("JPY")) pipSize = 0.01;
    if (trade.pair.includes("XAU")) pipSize = 0.01;

    // Correct pip value per lot
    let pipValuePerLot = 10.0;
    if (trade.pair.includes("XAU")) pipValuePerLot = 1.0;
    if (trade.pair.includes("JPY")) pipValuePerLot = 6.5;

    const pipValue = trade.lot_size * pipValuePerLot;

    let pips = 0;
    if (trade.direction === "BUY") {
      pips = (cp - trade.entry_price) / pipSize;
    } else {
      pips = (trade.entry_price - cp) / pipSize;
    }

    const pnl = Math.round(pips * pipValue * 100) / 100;
    const result = pnl > 0 ? "WIN" : pnl < 0 ? "LOSS" : "BREAKEVEN";
    
    console.log("Pips:", pips, "PnL:", pnl, "Result:", result);
    onClose(trade.id, result, pnl, Math.round(pips * 10) / 10);
    setShowInput(false);
  }
  
  if (!showInput) {
    return (
      <button
        onClick={() => setShowInput(true)}
        className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-2 py-1 rounded hover:bg-blue-600/30 transition-colors"
      >
        Close
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <input
        type="number"
        value={closePrice}
        onChange={(e) => setClosePrice(e.target.value)}
        placeholder="Close price"
        className="w-24 bg-gray-700 text-white text-xs px-2 py-1 rounded border border-gray-600"
      />
      <button
        onClick={handleClose}
        className="text-xs bg-green-600 text-white px-2 py-1 rounded"
      >
        ✓
      </button>
      <button
        onClick={() => setShowInput(false)}
        className="text-xs text-gray-400 px-1 py-1"
      >
        ✕
      </button>
    </div>
  );
}

function AddTradeModal({
  onClose,
  onAdded,
}: {
  onClose: () => void;
  onAdded: () => void;
}) {
  const [form, setForm] = useState({
    pair: "EUR/USD",
    direction: "BUY",
    entry_price: "",
    stop_loss: "",
    take_profit: "",
    lot_size: "",
    risk_amount: "",
    user_notes: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await journalApi.createTrade({
        ...form,
        entry_price: parseFloat(form.entry_price),
        stop_loss: parseFloat(form.stop_loss),
        take_profit: parseFloat(form.take_profit),
        lot_size: parseFloat(form.lot_size),
        risk_amount: parseFloat(form.risk_amount),
      });
      onAdded();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to add trade.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-white font-bold text-lg">Add Trade</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Pair</label>
              <select
                value={form.pair}
                onChange={(e) => update("pair", e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none"
              >
                {PAIRS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Direction</label>
              <select
                value={form.direction}
                onChange={(e) => update("direction", e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
          </div>

          {[
            { field: "entry_price", label: "Entry Price" },
            { field: "stop_loss", label: "Stop Loss" },
            { field: "take_profit", label: "Take Profit" },
            { field: "lot_size", label: "Lot Size" },
            { field: "risk_amount", label: "Risk Amount ($)" },
          ].map(({ field, label }) => (
            <div key={field}>
              <label className="block text-xs text-gray-400 mb-1">{label}</label>
              <input
                type="number"
                step="any"
                required
                value={form[field as keyof typeof form]}
                onChange={(e) => update(field, e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          ))}

          <div>
            <label className="block text-xs text-gray-400 mb-1">Notes</label>
            <textarea
              value={form.user_notes}
              onChange={(e) => update("user_notes", e.target.value)}
              rows={2}
              placeholder="Why did you take this trade?"
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder-gray-600 resize-none"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-bold py-2.5 rounded-lg transition-colors"
          >
            {loading ? "Adding..." : "Add Trade"}
          </button>
        </form>
      </div>
    </div>
  );
}