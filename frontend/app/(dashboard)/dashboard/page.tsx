"use client";
import { useEffect, useState } from "react";
import { useStore } from "@/store/useStore";
import { marketApi, analysisApi, journalApi } from "@/lib/api";
import { Signal, TradeStats } from "@/types";
import {
  formatCurrency,
  getDirectionBg,
  getConfidenceLabel,
} from "@/lib/utils-trading";
import { TrendingUp, Zap, BookOpen } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import Link from "next/link";

export default function DashboardPage() {
  const { user, activePair, setActivePair } = useStore();
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [quotes, setQuotes] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [quotesRes, signalsRes, statsRes] = await Promise.all([
          marketApi.getAllQuotes(),
          analysisApi.getSignals(),
          journalApi.getStats(),
        ]);
        setQuotes(quotesRes.data.quotes || {});
        setSignals(signalsRes.data || []);
        setStats(statsRes.data);
      } catch (err) {
        console.error("Dashboard load error:", err);
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  if (loading) return <LoadingSpinner />;

  const watchlist = user?.preferred_pairs || ["EUR/USD", "GBP/USD", "XAU/USD"];

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-bold text-white">
          Welcome back, {user?.display_name} 👋
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Here's your trading overview for today.
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">Account Balance</p>
          <p className="text-white text-xl font-bold">
            {formatCurrency(user?.account_balance || 0)}
          </p>
          <p className="text-yellow-400 text-xs mt-1">
            {user?.is_demo ? "Demo Account" : "Live Account"}
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">Total Trades</p>
          <p className="text-white text-xl font-bold">
            {stats?.total_trades || 0}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            {stats?.open_trades || 0} open
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">Win Rate</p>
          <p className="text-green-400 text-xl font-bold">
            {stats?.win_rate || 0}%
          </p>
          <p className="text-gray-500 text-xs mt-1">
            {stats?.wins || 0}W / {stats?.losses || 0}L
          </p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">Total PnL</p>
          <p
            className={`text-xl font-bold ${
              (stats?.total_pnl || 0) >= 0 ? "text-green-400" : "text-red-400"
            }`}
          >
            {formatCurrency(stats?.total_pnl || 0)}
          </p>
          <p className="text-gray-500 text-xs mt-1">
            Avg R:R {stats?.avg_rr || 0}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Watchlist */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-blue-400" />
            Watchlist
          </h2>
          <div className="space-y-2">
            {watchlist.map((pair) => {
              const quoteData = quotes[pair];
              const price = quoteData?.price ?? null;
              return (
                <button
                  key={pair}
                  onClick={() => setActivePair(pair)}
                  className={`w-full flex items-center justify-between p-3 rounded-lg transition-colors ${
                    activePair === pair
                      ? "bg-blue-600/20 border border-blue-600/30"
                      : "bg-gray-800 hover:bg-gray-700"
                  }`}
                >
                  <span className="text-white font-medium">{pair}</span>
                  <span className="text-gray-300 font-mono text-sm">
                    {price ? price.toFixed(pair.includes("JPY") ? 3 : pair.includes("XAU") ? 2 : 5) : "—"}
                  </span>
                </button>
              );
            })}
          </div>
          <Link
            href="/market"
            className="block text-center text-blue-400 text-sm mt-4 hover:text-blue-300"
          >
            Open Chart →
          </Link>
        </div>

        {/* AI Signals */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Zap className="h-4 w-4 text-yellow-400" />
            Active AI Signals
          </h2>
          {signals.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500 text-sm">No active signals yet.</p>
              <Link
                href="/signals"
                className="text-blue-400 text-sm hover:text-blue-300 mt-2 block"
              >
                Generate a signal →
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {signals.slice(0, 4).map((signal) => {
                const conf = getConfidenceLabel(signal.confidence_score || 0);
                return (
                  <div
                    key={signal.id}
                    className="flex items-center justify-between p-3 bg-gray-800 rounded-lg"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded border ${getDirectionBg(signal.direction)}`}
                      >
                        {signal.direction}
                      </span>
                      <span className="text-white text-sm">{signal.pair}</span>
                    </div>
                    <span className={`text-xs ${conf.color}`}>
                      {signal.confidence_score}% {conf.label}
                    </span>
                  </div>
                );
              })}
              <Link
                href="/signals"
                className="block text-center text-blue-400 text-sm mt-2 hover:text-blue-300"
              >
                View all signals →
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <Link
          href="/signals"
          className="bg-blue-600/10 border border-blue-600/30 rounded-xl p-4 hover:bg-blue-600/20 transition-colors"
        >
          <Zap className="h-6 w-6 text-blue-400 mb-2" />
          <p className="text-white font-medium text-sm">Generate AI Signal</p>
          <p className="text-gray-400 text-xs mt-1">
            Analyze any pair with AI
          </p>
        </Link>
        <Link
          href="/risk-calculator"
          className="bg-green-600/10 border border-green-600/30 rounded-xl p-4 hover:bg-green-600/20 transition-colors"
        >
          <TrendingUp className="h-6 w-6 text-green-400 mb-2" />
          <p className="text-white font-medium text-sm">Risk Calculator</p>
          <p className="text-gray-400 text-xs mt-1">
            Calculate lot size & risk
          </p>
        </Link>
        <Link
          href="/journal"
          className="bg-purple-600/10 border border-purple-600/30 rounded-xl p-4 hover:bg-purple-600/20 transition-colors"
        >
          <BookOpen className="h-6 w-6 text-purple-400 mb-2" />
          <p className="text-white font-medium text-sm">Trade Journal</p>
          <p className="text-gray-400 text-xs mt-1">Track your trades</p>
        </Link>
      </div>
    </div>
  );
}