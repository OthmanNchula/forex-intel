"use client";
import { useEffect, useState } from "react";
import { authApi, journalApi } from "@/lib/api";
import { Trade, TradeStats } from "@/types";
import {
  formatCurrency,
  formatDate,
  getDirectionBg,
  getResultColor,
  getPnLColor,
} from "@/lib/utils-trading";
import { BookOpen, Plus, X, TrendingUp, Trash2, Wallet, Target, Gauge, Pencil } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { useStore } from "@/store/useStore";
import { saveAuth, getToken } from "@/lib/auth";
import { StatCard } from "@/components/ui/stat-card";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD"];

export default function JournalPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingTrade, setEditingTrade] = useState<Trade | null>(null);
  const [filterResult, setFilterResult] = useState("");
  const setUser = useStore((s) => s.setUser);

  useEffect(() => {
    loadJournal();
  }, []);

  // Re-fetch the current user (balance included) and sync it into the
  // store + localStorage cache so the header updates immediately.
  async function refreshUser() {
    try {
      const res = await authApi.me();
      setUser(res.data);
      const token = getToken();
      if (token) saveAuth(token, res.data);
    } catch (err) {
      console.error("User refresh error:", err);
    }
  }

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
    pnlPips: number,
    closePrice: number
  ) {
    try {
      await journalApi.updateTrade(id, {
        close_price: closePrice,
        result,
        pnl,
        pnl_pips: pnlPips,
        closed_at: new Date().toISOString(),
      });
      await Promise.all([loadJournal(), refreshUser()]);
    } catch (err) {
      console.error("Close trade error:", err);
    }
  }

  async function deleteTrade(id: string) {
    if (!confirm("Delete this trade?")) return;
    try {
      await journalApi.deleteTrade(id);
      setTrades((prev) => prev.filter((t) => t.id !== id));
      // Deleting a closed trade reverses its balance effect server-side too.
      refreshUser();
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 animate-in fade-in slide-in-from-bottom-2 duration-500">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-purple-400" />
            Trade Journal
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Track and review all your trades
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={async () => {
              if (
                !confirm(
                  "Delete ALL trades in your journal? This cannot be undone. Your balance is untouched — use Fix Balance afterwards to reset it to a fresh starting amount."
                )
              )
                return;
              try {
                await journalApi.clearAllTrades();
                await loadJournal();
              } catch (err) {
                console.error("Clear all trades error:", err);
              }
            }}
            className="flex items-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-300 font-medium px-3 py-2 text-sm rounded-xl transition-all duration-200 ring-1 ring-red-500/25 hover:ring-red-500/40 whitespace-nowrap"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear All Trades
          </button>
          <button
            onClick={async () => {
              const input = prompt(
                "Set your starting balance (e.g. match your real/demo broker account). Your balance will be recalculated as this amount + the total PnL of all closed trades:",
                "10000"
              );
              if (input === null) return; // cancelled
              const startingBalance = parseFloat(input);
              if (isNaN(startingBalance) || startingBalance < 0) {
                alert("Please enter a valid positive number.");
                return;
              }
              try {
                await journalApi.recalculateBalance(startingBalance);
                await refreshUser();
              } catch (err) {
                console.error("Recalculate balance error:", err);
              }
            }}
            className="flex items-center gap-2 bg-white/[0.05] hover:bg-white/[0.09] text-gray-200 font-medium px-3 py-2 text-sm rounded-xl transition-all duration-200 ring-1 ring-white/[0.08] hover:ring-white/[0.15] whitespace-nowrap"
          >
            <Wallet className="h-3.5 w-3.5" />
            Fix Balance
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 text-white font-medium px-3 py-2 text-sm rounded-xl transition-all duration-200 shadow-lg shadow-purple-600/20 whitespace-nowrap"
          >
            <Plus className="h-4 w-4" />
            Add Trade
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={BookOpen}
            label="Total Trades"
            value={stats.total_trades}
            sublabel={`${stats.open_trades} open`}
            accent="blue"
            delay={0}
          />
          <StatCard
            icon={Target}
            label="Win Rate"
            value={`${stats.win_rate}%`}
            sublabel={`${stats.wins}W / ${stats.losses}L`}
            accent="green"
            valueClassName="text-green-400"
            delay={60}
          />
          <StatCard
            icon={TrendingUp}
            label="Total PnL"
            value={formatCurrency(stats.total_pnl)}
            accent={stats.total_pnl >= 0 ? "green" : "red"}
            valueClassName={getPnLColor(stats.total_pnl)}
            delay={120}
          />
          <StatCard
            icon={Gauge}
            label="Avg R:R"
            value={stats.avg_rr}
            accent="purple"
            delay={180}
          />
        </div>
      )}

      {/* Filter */}
      <div className="flex flex-wrap gap-2">
        {["", "OPEN", "WIN", "LOSS", "BREAKEVEN"].map((f) => (
          <button
            key={f}
            onClick={() => setFilterResult(f)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 ${
              filterResult === f
                ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg shadow-blue-600/20"
                : "bg-white/[0.04] text-gray-400 hover:text-white ring-1 ring-white/[0.06] hover:ring-white/[0.12]"
            }`}
          >
            {f || "All"}
          </button>
        ))}
      </div>

      {/* Trades table */}
      <div className="glass-card overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-16">
            <div className="h-14 w-14 rounded-2xl bg-white/[0.04] ring-1 ring-white/[0.06] flex items-center justify-center mx-auto mb-4">
              <BookOpen className="h-6 w-6 text-gray-600" />
            </div>
            <p className="text-gray-500">No trades found.</p>
            <button
              onClick={() => setShowForm(true)}
              className="mt-3 text-purple-400 hover:text-purple-300 text-sm transition-colors"
            >
              Add your first trade →
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-gray-500 text-[11px] uppercase tracking-wider">
                  <th className="text-left px-4 py-3 font-medium">Pair</th>
                  <th className="text-left px-4 py-3 font-medium">Direction</th>
                  <th className="text-left px-4 py-3 font-medium">Entry</th>
                  <th className="text-left px-4 py-3 font-medium">SL</th>
                  <th className="text-left px-4 py-3 font-medium">TP</th>
                  <th className="text-left px-4 py-3 font-medium">Lots</th>
                  <th className="text-left px-4 py-3 font-medium">Risk</th>
                  <th className="text-left px-4 py-3 font-medium">Result</th>
                  <th className="text-left px-4 py-3 font-medium">PnL</th>
                  <th className="text-left px-4 py-3 font-medium">Date</th>
                  <th className="text-left px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((trade) => (
                  <tr
                    key={trade.id}
                    className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors"
                  >
                    <td className="px-4 py-3 text-white font-medium">
                      {trade.pair}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded-md border ${getDirectionBg(trade.direction)}`}
                      >
                        {trade.direction}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-300 font-mono tabular-nums">
                      {trade.entry_price}
                    </td>
                    <td className="px-4 py-3 text-red-400 font-mono tabular-nums">
                      {trade.stop_loss}
                    </td>
                    <td className="px-4 py-3 text-green-400 font-mono tabular-nums">
                      {trade.take_profit}
                    </td>
                    <td className="px-4 py-3 text-gray-300 tabular-nums">
                      {trade.lot_size}
                    </td>
                    <td className="px-4 py-3 text-gray-300 tabular-nums">
                      {formatCurrency(trade.risk_amount)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded-md border ${getResultColor(trade.result)}`}
                      >
                        {trade.result}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-mono font-bold tabular-nums ${getPnLColor(trade.pnl || 0)}`}
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
                          onClick={() => setEditingTrade(trade)}
                          className="text-gray-500 hover:text-blue-400 transition-colors"
                          title="Edit trade"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => deleteTrade(trade.id)}
                          className="text-gray-600 hover:text-red-400 transition-colors"
                          title="Delete trade"
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
        <TradeFormModal
          onClose={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            // Adding a trade can resolve it (WIN/LOSS) immediately and
            // update the balance server-side, so refresh it here too.
            Promise.all([loadJournal(), refreshUser()]);
          }}
        />
      )}

      {/* Edit Trade Modal */}
      {editingTrade && (
        <TradeFormModal
          trade={editingTrade}
          onClose={() => setEditingTrade(null)}
          onSaved={() => {
            setEditingTrade(null);
            // Editing a closed trade's numbers can change its pnl and the
            // account balance server-side (see update_trade()), so refresh
            // both, same as adding a trade.
            Promise.all([loadJournal(), refreshUser()]);
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
  onClose: (
    id: string,
    result: string,
    pnl: number,
    pnlPips: number,
    closePrice: number
  ) => void;
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
    onClose(trade.id, result, pnl, Math.round(pips * 10) / 10, cp);
    setShowInput(false);
  }
  
  if (!showInput) {
    return (
      <button
        onClick={() => setShowInput(true)}
        className="text-xs bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/25 px-2.5 py-1 rounded-full hover:bg-blue-500/20 transition-colors font-medium"
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
        className="w-24 bg-white/[0.06] text-white text-xs px-2 py-1 rounded-lg ring-1 ring-white/[0.1] focus:ring-blue-500/50 focus:outline-none placeholder-gray-600"
      />
      <button
        onClick={handleClose}
        className="text-xs bg-green-600 hover:bg-green-500 text-white px-2 py-1 rounded-lg transition-colors"
      >
        ✓
      </button>
      <button
        onClick={() => setShowInput(false)}
        className="text-xs text-gray-500 hover:text-gray-300 px-1 py-1 transition-colors"
      >
        ✕
      </button>
    </div>
  );
}

function TradeFormModal({
  trade,
  onClose,
  onSaved,
}: {
  trade?: Trade | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!trade;
  const isClosed = !!trade && trade.result !== "OPEN";

  const [form, setForm] = useState({
    pair: trade?.pair || "EUR/USD",
    direction: trade?.direction || "BUY",
    entry_price: trade ? String(trade.entry_price) : "",
    stop_loss: trade ? String(trade.stop_loss) : "",
    take_profit: trade ? String(trade.take_profit) : "",
    lot_size: trade ? String(trade.lot_size) : "",
    risk_amount: trade ? String(trade.risk_amount) : "",
    close_price: trade?.close_price != null ? String(trade.close_price) : "",
    user_notes: trade?.user_notes || "",
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
      if (isEdit && trade) {
        const payload: Record<string, any> = {
          pair: form.pair,
          direction: form.direction,
          entry_price: parseFloat(form.entry_price),
          stop_loss: parseFloat(form.stop_loss),
          take_profit: parseFloat(form.take_profit),
          lot_size: parseFloat(form.lot_size),
          risk_amount: parseFloat(form.risk_amount),
          user_notes: form.user_notes,
        };
        // Only a closed trade has a close price to correct — the backend
        // recomputes pnl (and adjusts the balance by the difference)
        // whenever any of these numbers change on an already-closed trade.
        if (isClosed && form.close_price !== "") {
          payload.close_price = parseFloat(form.close_price);
        }
        await journalApi.updateTrade(trade.id, payload);
      } else {
        await journalApi.createTrade({
          pair: form.pair,
          direction: form.direction,
          entry_price: parseFloat(form.entry_price),
          stop_loss: parseFloat(form.stop_loss),
          take_profit: parseFloat(form.take_profit),
          lot_size: parseFloat(form.lot_size),
          risk_amount: parseFloat(form.risk_amount),
          user_notes: form.user_notes,
        });
      }
      onSaved();
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          (isEdit ? "Failed to save changes." : "Failed to add trade.")
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
      <div className="glass-card p-6 w-full max-w-md animate-in zoom-in-95 slide-in-from-bottom-4 duration-300">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-white font-bold text-lg">
            {isEdit ? "Edit Trade" : "Add Trade"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="h-5 w-5" />
          </button>
        </div>

        {isEdit && (
          <p className="text-gray-500 text-xs mb-4 -mt-2">
            {isClosed
              ? "This trade is closed — correcting any number below recalculates its PnL and adjusts your balance to match."
              : "This trade is still open — corrections apply immediately."}
          </p>
        )}

        {error && (
          <div className="bg-red-500/10 ring-1 ring-red-500/30 rounded-xl p-3 mb-4">
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
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
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
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
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
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
              />
            </div>
          ))}

          {isClosed && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">
                Close Price
              </label>
              <input
                type="number"
                step="any"
                value={form.close_price}
                onChange={(e) => update("close_price", e.target.value)}
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 transition-shadow"
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-gray-400 mb-1">Notes</label>
            <textarea
              value={form.user_notes}
              onChange={(e) => update("user_notes", e.target.value)}
              rows={2}
              placeholder="Why did you take this trade?"
              className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-blue-500/50 placeholder-gray-600 resize-none transition-shadow"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 disabled:opacity-50 text-white font-bold py-2.5 rounded-xl transition-all duration-200 shadow-lg shadow-purple-600/20"
          >
            {loading
              ? isEdit
                ? "Saving..."
                : "Adding..."
              : isEdit
              ? "Save Changes"
              : "Add Trade"}
          </button>
        </form>
      </div>
    </div>
  );
}