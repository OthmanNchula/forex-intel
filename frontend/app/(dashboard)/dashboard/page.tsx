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
import { TrendingUp, TrendingDown, Zap, BookOpen, Cpu, Wallet, Target, PieChart, ArrowRight } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import Link from "next/link";
import { StatCard } from "@/components/ui/stat-card";
import { SectionCard } from "@/components/ui/section-card";

interface AiUsage {
  daily_used: number;
  daily_budget: number;
  daily_remaining: number;
  monthly_used: number;
  monthly_budget: number;
  monthly_remaining: number;
}

export default function DashboardPage() {
  const { user, activePair, setActivePair } = useStore();
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [quotes, setQuotes] = useState<Record<string, any>>({});
  const [aiUsage, setAiUsage] = useState<AiUsage | null>(null);
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

    // Separate, non-blocking load — a failure here (e.g. Redis hiccup)
    // shouldn't take down the rest of the dashboard.
    analysisApi
      .getAiUsage()
      .then((res) => setAiUsage(res.data))
      .catch((err) => console.error("AI usage load error:", err));
  }, []);

  if (loading) return <LoadingSpinner />;

  const watchlist = user?.preferred_pairs || ["EUR/USD", "GBP/USD", "XAU/USD"];
  const pnl = stats?.total_pnl || 0;

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <h1 className="text-2xl font-bold text-white">
          Welcome back, {user?.display_name} <span className="inline-block animate-[wave_1.5s_ease-in-out_1]">👋</span>
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Here's your trading overview for today.
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={Wallet}
          label="Account Balance"
          value={formatCurrency(user?.account_balance || 0)}
          sublabel={user?.is_demo ? "Demo Account" : "Live Account"}
          accent="amber"
          delay={0}
        />
        <StatCard
          icon={PieChart}
          label="Total Trades"
          value={stats?.total_trades || 0}
          sublabel={`${stats?.open_trades || 0} open`}
          accent="blue"
          delay={60}
        />
        <StatCard
          icon={Target}
          label="Win Rate"
          value={`${stats?.win_rate || 0}%`}
          sublabel={`${stats?.wins || 0}W / ${stats?.losses || 0}L`}
          accent="green"
          valueClassName="text-green-400"
          delay={120}
        />
        <StatCard
          icon={pnl >= 0 ? TrendingUp : TrendingDown}
          label="Total PnL"
          value={formatCurrency(pnl)}
          sublabel={`Avg R:R ${stats?.avg_rr || 0}`}
          accent={pnl >= 0 ? "green" : "red"}
          valueClassName={pnl >= 0 ? "text-green-400" : "text-red-400"}
          delay={180}
        />
      </div>

      {/* AI usage — daily/monthly call budget against the hard caps in
          auto_signal_engine.py, so the spending limit isn't invisible */}
      {aiUsage && (
        <SectionCard
          icon={Cpu}
          iconClassName="text-blue-400"
          title="AI Analysis Usage"
          delay={220}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UsageBar
              label="Today"
              used={aiUsage.daily_used}
              budget={aiUsage.daily_budget}
            />
            <UsageBar
              label="This Month"
              used={aiUsage.monthly_used}
              budget={aiUsage.monthly_budget}
            />
          </div>
          {aiUsage.daily_used >= aiUsage.daily_budget && (
            <p className="text-amber-400 text-xs mt-3 flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
              Today's AI budget is used up — signals are running on
              technical-only analysis (no AI confirmation) until it
              resets tomorrow.
            </p>
          )}
        </SectionCard>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Watchlist */}
        <SectionCard
          icon={TrendingUp}
          iconClassName="text-blue-400"
          title="Watchlist"
          delay={260}
        >
          <div className="space-y-2">
            {watchlist.map((pair, i) => {
              const quoteData = quotes[pair];
              const price = quoteData?.price ?? null;
              const isActive = activePair === pair;
              return (
                <button
                  key={pair}
                  onClick={() => setActivePair(pair)}
                  className={`group w-full flex items-center justify-between p-3 rounded-xl transition-all duration-200 animate-in fade-in slide-in-from-left-2 ${
                    isActive
                      ? "bg-gradient-to-r from-blue-600/20 to-purple-600/10 ring-1 ring-blue-500/30 shadow-[0_0_16px_-6px_rgba(59,130,246,0.5)]"
                      : "bg-white/[0.03] hover:bg-white/[0.06] ring-1 ring-white/[0.04] hover:ring-white/[0.08]"
                  }`}
                  style={{ animationDelay: `${300 + i * 40}ms`, animationDuration: "400ms", animationFillMode: "backwards" }}
                >
                  <span className={`font-medium transition-colors ${isActive ? "text-blue-300" : "text-white"}`}>
                    {pair}
                  </span>
                  <span className="text-gray-300 font-mono text-sm tabular-nums">
                    {price ? price.toFixed(pair.includes("JPY") ? 3 : pair.includes("XAU") ? 2 : 5) : "—"}
                  </span>
                </button>
              );
            })}
          </div>
          <Link
            href="/market"
            className="group flex items-center justify-center gap-1 text-blue-400 text-sm mt-4 hover:text-blue-300 transition-colors"
          >
            Open Chart
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </SectionCard>

        {/* AI Signals */}
        <SectionCard
          icon={Zap}
          iconClassName="text-yellow-400"
          title="Active AI Signals"
          delay={300}
        >
          {signals.length === 0 ? (
            <div className="text-center py-8">
              <div className="h-10 w-10 rounded-full bg-white/[0.04] ring-1 ring-white/[0.06] flex items-center justify-center mx-auto mb-3">
                <Zap className="h-5 w-5 text-gray-600" />
              </div>
              <p className="text-gray-500 text-sm">No active signals yet.</p>
              <Link
                href="/signals"
                className="text-blue-400 text-sm hover:text-blue-300 mt-2 inline-block transition-colors"
              >
                Generate a signal →
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {signals.slice(0, 4).map((signal, i) => {
                const conf = getConfidenceLabel(signal.confidence_score || 0);
                const isBuy = signal.direction === "BUY";
                return (
                  <div
                    key={signal.id}
                    className={`flex items-center justify-between p-3 bg-white/[0.03] hover:bg-white/[0.06] rounded-xl transition-all duration-200 border-l-2 animate-in fade-in slide-in-from-right-2 ${
                      isBuy ? "border-l-green-500/50" : "border-l-red-500/50"
                    }`}
                    style={{ animationDelay: `${340 + i * 50}ms`, animationDuration: "400ms", animationFillMode: "backwards" }}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded-md border ${getDirectionBg(signal.direction)}`}
                      >
                        {signal.direction}
                      </span>
                      <span className="text-white text-sm font-medium">{signal.pair}</span>
                    </div>
                    <span className={`text-xs font-medium ${conf.color}`}>
                      {signal.confidence_score}% {conf.label}
                    </span>
                  </div>
                );
              })}
              <Link
                href="/signals"
                className="group flex items-center justify-center gap-1 text-blue-400 text-sm mt-2 hover:text-blue-300 transition-colors"
              >
                View all signals
                <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>
          )}
        </SectionCard>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <QuickAction
          href="/signals"
          icon={Zap}
          accent="blue"
          title="Generate AI Signal"
          subtitle="Analyze any pair with AI"
          delay={380}
        />
        <QuickAction
          href="/risk-calculator"
          icon={TrendingUp}
          accent="green"
          title="Risk Calculator"
          subtitle="Calculate lot size & risk"
          delay={420}
        />
        <QuickAction
          href="/journal"
          icon={BookOpen}
          accent="purple"
          title="Trade Journal"
          subtitle="Track your trades"
          delay={460}
        />
      </div>
    </div>
  );
}

function QuickAction({
  href,
  icon: Icon,
  accent,
  title,
  subtitle,
  delay,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: "blue" | "green" | "purple";
  title: string;
  subtitle: string;
  delay: number;
}) {
  const accentMap = {
    blue: {
      wrap: "bg-blue-600/[0.08] hover:bg-blue-600/[0.14] ring-1 ring-blue-600/20 hover:ring-blue-600/35",
      icon: "text-blue-400",
    },
    green: {
      wrap: "bg-green-600/[0.08] hover:bg-green-600/[0.14] ring-1 ring-green-600/20 hover:ring-green-600/35",
      icon: "text-green-400",
    },
    purple: {
      wrap: "bg-purple-600/[0.08] hover:bg-purple-600/[0.14] ring-1 ring-purple-600/20 hover:ring-purple-600/35",
      icon: "text-purple-400",
    },
  }[accent];

  return (
    <Link
      href={href}
      className={`group rounded-2xl p-4 transition-all duration-300 hover:-translate-y-0.5 animate-in fade-in slide-in-from-bottom-2 ${accentMap.wrap}`}
      style={{ animationDelay: `${delay}ms`, animationDuration: "500ms", animationFillMode: "backwards" }}
    >
      <Icon className={`h-6 w-6 mb-2 transition-transform duration-300 group-hover:scale-110 ${accentMap.icon}`} />
      <p className="text-white font-medium text-sm">{title}</p>
      <p className="text-gray-400 text-xs mt-1">{subtitle}</p>
    </Link>
  );
}

function UsageBar({
  label,
  used,
  budget,
}: {
  label: string;
  used: number;
  budget: number;
}) {
  const pct = budget > 0 ? Math.min(100, Math.round((used / budget) * 100)) : 0;
  const barColor =
    pct >= 100 ? "bg-gradient-to-r from-red-500 to-red-400" : pct >= 80 ? "bg-gradient-to-r from-amber-500 to-amber-400" : "bg-gradient-to-r from-blue-500 to-purple-500";

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-gray-400 text-xs font-medium">{label}</span>
        <span className="text-gray-300 text-xs font-mono tabular-nums">
          {used} / {budget} calls
        </span>
      </div>
      <div className="bg-white/[0.05] rounded-full h-2 overflow-hidden">
        <div
          className={`h-2 rounded-full ${barColor} transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
