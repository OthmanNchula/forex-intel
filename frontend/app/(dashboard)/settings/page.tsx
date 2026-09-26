"use client";
import { useState } from "react";
import { useStore } from "@/store/useStore";
import { authApi } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { Settings, User, Shield, Bell, Info } from "lucide-react";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD", "USD/CHF"];
const TIMEZONES = [
  "Africa/Dar_es_Salaam",
  "Africa/Nairobi",
  "Africa/Lagos",
  "Europe/London",
  "America/New_York",
  "Asia/Tokyo",
];

export default function SettingsPage() {
  const { user, setUser } = useStore();
  const [displayName, setDisplayName] = useState(user?.display_name || "");
  const [balance, setBalance] = useState(user?.account_balance?.toString() || "10000");
  const [riskPct, setRiskPct] = useState(user?.risk_per_trade_pct?.toString() || "1");
  const [maxDailyRisk, setMaxDailyRisk] = useState(user?.max_daily_risk_pct?.toString() || "3");
  const [timezone, setTimezone] = useState(user?.timezone || "Africa/Dar_es_Salaam");
  const [selectedPairs, setSelectedPairs] = useState<string[]>(
    user?.preferred_pairs || ["EUR/USD", "GBP/USD", "XAU/USD"]
  );
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  function togglePair(pair: string) {
    setSelectedPairs((prev) =>
      prev.includes(pair) ? prev.filter((p) => p !== pair) : [...prev, pair]
    );
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const res = await authApi.updateMe({
        display_name: displayName,
        account_balance: parseFloat(balance),
        risk_per_trade_pct: parseFloat(riskPct),
        max_daily_risk_pct: parseFloat(maxDailyRisk),
        timezone,
        preferred_pairs: selectedPairs,
      });
      const updatedUser = res.data;
      setUser(updatedUser);
      // Update localStorage
      const token = localStorage.getItem("forex_intel_token") || "";
      saveAuth(token, updatedUser);
      setSuccess("Settings saved successfully!");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to save settings.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Settings className="h-6 w-6 text-gray-400" />
          Settings
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Manage your profile and trading preferences
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Profile */}
        <div
          className="glass-card p-6 animate-in fade-in slide-in-from-bottom-2"
          style={{ animationDelay: "60ms", animationDuration: "500ms", animationFillMode: "backwards" }}
        >
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <User className="h-4 w-4 text-blue-400" />
            Profile
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Display Name
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-blue-500/50 transition-shadow"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={user?.email || ""}
                disabled
                className="w-full bg-white/[0.02] ring-1 ring-white/[0.06] text-gray-500 rounded-xl px-4 py-2.5 cursor-not-allowed"
              />
              <p className="text-gray-600 text-xs mt-1">
                Email cannot be changed
              </p>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Timezone
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-blue-500/50 transition-shadow"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Trading Settings */}
        <div
          className="glass-card p-6 animate-in fade-in slide-in-from-bottom-2"
          style={{ animationDelay: "120ms", animationDuration: "500ms", animationFillMode: "backwards" }}
        >
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Shield className="h-4 w-4 text-green-400" />
            Risk Management
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Demo Account Balance ($)
              </label>
              <input
                type="number"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
                min="100"
                step="100"
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 transition-shadow"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Default Risk % per Trade
              </label>
              <input
                type="number"
                value={riskPct}
                onChange={(e) => setRiskPct(e.target.value)}
                min="0.1"
                max="5"
                step="0.1"
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 transition-shadow"
              />
              <p className="text-gray-600 text-xs mt-1">
                Recommended: 1-2% per trade
              </p>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Max Daily Risk %
              </label>
              <input
                type="number"
                value={maxDailyRisk}
                onChange={(e) => setMaxDailyRisk(e.target.value)}
                min="1"
                max="10"
                step="0.5"
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] text-white rounded-xl px-4 py-2.5 focus:outline-none focus:ring-green-500/50 transition-shadow"
              />
              <p className="text-gray-600 text-xs mt-1">
                System will warn you when daily risk exceeds this limit
              </p>
            </div>
          </div>
        </div>

        {/* Watchlist */}
        <div
          className="glass-card p-6 animate-in fade-in slide-in-from-bottom-2"
          style={{ animationDelay: "180ms", animationDuration: "500ms", animationFillMode: "backwards" }}
        >
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Bell className="h-4 w-4 text-yellow-400" />
            Watchlist Pairs
          </h2>
          <p className="text-gray-400 text-xs mb-4">
            Select the pairs you want to track on your dashboard
          </p>
          <div className="flex flex-wrap gap-2">
            {PAIRS.map((pair) => (
              <button
                key={pair}
                type="button"
                onClick={() => togglePair(pair)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                  selectedPairs.includes(pair)
                    ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md shadow-blue-600/20"
                    : "bg-white/[0.04] text-gray-400 ring-1 ring-white/[0.08] hover:text-white hover:ring-white/[0.15]"
                }`}
              >
                {pair}
              </button>
            ))}
          </div>
        </div>

        {/* Disclaimer */}
        <div
          className="glass-card p-6 animate-in fade-in slide-in-from-bottom-2"
          style={{ animationDelay: "240ms", animationDuration: "500ms", animationFillMode: "backwards" }}
        >
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Info className="h-4 w-4 text-gray-400" />
            About Forex Intel
          </h2>
          <div className="space-y-2 text-gray-400 text-sm">
            <p>Version: 1.0.0</p>
            <p>Backend: FastAPI + PostgreSQL + Redis</p>
            <p>AI Engine: Claude claude-sonnet-4-6</p>
            <p>Market Data: Twelve Data API</p>
          </div>
          <div className="mt-4 bg-amber-500/[0.07] ring-1 ring-amber-500/25 rounded-xl p-3">
            <p className="text-amber-400/90 text-xs">
              ⚠️ Forex Intel is a decision-support tool only. All signals and
              analysis are NOT financial advice. Always use a demo account
              before trading live. Trading Forex involves significant risk of
              loss.
            </p>
          </div>
        </div>

        {success && (
          <div className="bg-green-500/10 ring-1 ring-green-500/30 rounded-xl p-3 animate-in fade-in slide-in-from-top-1 duration-300">
            <p className="text-green-400 text-sm">✅ {success}</p>
          </div>
        )}

        {error && (
          <div className="bg-red-500/10 ring-1 ring-red-500/30 rounded-xl p-3">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 text-white font-bold py-3 rounded-xl transition-all duration-200 shadow-lg shadow-blue-600/20"
        >
          {loading ? "Saving..." : "Save Settings"}
        </button>
      </form>
    </div>
  );
}