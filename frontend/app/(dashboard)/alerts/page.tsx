"use client";
import { useState } from "react";
import { useAlerts } from "@/hooks/useAlerts";
import { Alert } from "@/types";
import { Bell, Plus, X, CheckCircle, Clock } from "lucide-react";
import { formatDate } from "@/lib/utils-trading";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

const PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD"];
const ALERT_TYPES = [
  { value: "PRICE", label: "Price Level" },
  { value: "RSI", label: "RSI Extreme" },
  { value: "EMA_CROSS", label: "EMA Crossover" },
  { value: "NEW_SIGNAL", label: "New AI Signal" },
];

export default function AlertsPage() {
  const { alerts, notifications, loading, createAlert, deleteAlert } = useAlerts();
  const [showForm, setShowForm] = useState(false);
  const [pair, setPair] = useState("EUR/USD");
  const [alertType, setAlertType] = useState("PRICE");
  const [conditionValue, setConditionValue] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await createAlert({
        pair,
        alert_type: alertType,
        condition_value: conditionValue ? parseFloat(conditionValue) : undefined,
        message: message || undefined,
      });
      setSuccess("Alert created successfully!");
      setShowForm(false);
      setConditionValue("");
      setMessage("");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create alert.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bell className="h-6 w-6 text-yellow-400" />
            Alerts
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Get notified when market conditions match your criteria
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-yellow-500 hover:bg-yellow-400 text-black font-bold px-4 py-2 rounded-lg transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Alert
        </button>
      </div>

      {success && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
          <p className="text-green-400 text-sm">✅ {success}</p>
        </div>
      )}

      {/* Create Alert Form */}
      {showForm && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4">Create New Alert</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
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
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  Alert Type
                </label>
                <select
                  value={alertType}
                  onChange={(e) => setAlertType(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500"
                >
                  {ALERT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {alertType === "PRICE" && (
              <div>
                <label className="block text-sm text-gray-400 mb-1.5">
                  Target Price
                </label>
                <input
                  type="number"
                  value={conditionValue}
                  onChange={(e) => setConditionValue(e.target.value)}
                  step="0.00001"
                  required
                  placeholder="e.g. 1.09500"
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
                />
              </div>
            )}

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Custom Message (optional)
              </label>
              <input
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="e.g. EUR/USD reached my entry zone"
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 bg-yellow-500 hover:bg-yellow-400 disabled:opacity-50 text-black font-bold py-2.5 rounded-lg transition-colors"
              >
                {saving ? "Creating..." : "Create Alert"}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2.5 bg-gray-800 text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Active Alerts */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Clock className="h-4 w-4 text-blue-400" />
            Active Alerts ({alerts.filter((a) => !a.is_triggered).length})
          </h2>
          {alerts.filter((a) => !a.is_triggered).length === 0 ? (
            <div className="text-center py-8">
              <Bell className="h-10 w-10 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">No active alerts.</p>
              <button
                onClick={() => setShowForm(true)}
                className="mt-2 text-yellow-400 hover:text-yellow-300 text-sm"
              >
                Create your first alert →
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {alerts
                .filter((a) => !a.is_triggered)
                .map((alert) => (
                  <AlertItem
                    key={alert.id}
                    alert={alert}
                    onDelete={deleteAlert}
                  />
                ))}
            </div>
          )}
        </div>

        {/* Triggered Alerts */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-400" />
            Triggered Alerts ({alerts.filter((a) => a.is_triggered).length})
          </h2>
          {alerts.filter((a) => a.is_triggered).length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle className="h-10 w-10 text-gray-700 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">No triggered alerts yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {alerts
                .filter((a) => a.is_triggered)
                .map((alert) => (
                  <AlertItem
                    key={alert.id}
                    alert={alert}
                    onDelete={deleteAlert}
                  />
                ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Notifications */}
      {notifications.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Bell className="h-4 w-4 text-yellow-400" />
            Recent Notifications
          </h2>
          <div className="space-y-2">
            {notifications.map((n, i) => (
              <div
                key={i}
                className="flex items-center justify-between bg-gray-800 rounded-lg p-3"
              >
                <div>
                  <p className="text-white text-sm">{n.message || n.type}</p>
                  <p className="text-gray-500 text-xs mt-0.5">{n.pair}</p>
                </div>
                <span className="text-gray-600 text-xs">
                  {n.timestamp
                    ? new Date(n.timestamp).toLocaleTimeString()
                    : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alert Types Guide */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h2 className="text-white font-semibold mb-4">Alert Types Guide</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            {
              type: "PRICE",
              label: "Price Level",
              desc: "Triggers when price crosses your target level",
              color: "text-blue-400",
            },
            {
              type: "RSI",
              label: "RSI Extreme",
              desc: "Triggers when RSI enters overbought (>70) or oversold (<30)",
              color: "text-purple-400",
            },
            {
              type: "EMA_CROSS",
              label: "EMA Crossover",
              desc: "Triggers when EMA20 crosses EMA50 in either direction",
              color: "text-yellow-400",
            },
            {
              type: "NEW_SIGNAL",
              label: "New AI Signal",
              desc: "Triggers when a high-confidence AI signal is generated",
              color: "text-green-400",
            },
          ].map(({ type, label, desc, color }) => (
            <div key={type} className="bg-gray-800 rounded-lg p-4">
              <p className={`font-medium text-sm mb-1 ${color}`}>{label}</p>
              <p className="text-gray-400 text-xs">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AlertItem({
  alert,
  onDelete,
}: {
  alert: Alert;
  onDelete: (id: string) => void;
}) {
  const typeColors: Record<string, string> = {
    PRICE: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    RSI: "text-purple-400 bg-purple-500/10 border-purple-500/30",
    EMA_CROSS: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
    NEW_SIGNAL: "text-green-400 bg-green-500/10 border-green-500/30",
    SL_HIT: "text-red-400 bg-red-500/10 border-red-500/30",
    TP_HIT: "text-green-400 bg-green-500/10 border-green-500/30",
  };

  const colorClass = typeColors[alert.alert_type] || "text-gray-400 bg-gray-500/10 border-gray-500/30";

  return (
    <div
      className={`flex items-center justify-between p-3 rounded-lg border ${
        alert.is_triggered ? "opacity-60" : ""
      } bg-gray-800 border-gray-700`}
    >
      <div className="flex items-center gap-3">
        <span
          className={`text-xs font-bold px-2 py-0.5 rounded border ${colorClass}`}
        >
          {alert.alert_type.replace("_", " ")}
        </span>
        <div>
          <p className="text-white text-sm font-medium">{alert.pair}</p>
          {alert.condition_value && (
            <p className="text-gray-400 text-xs">
              Target: {alert.condition_value}
            </p>
          )}
          {alert.message && (
            <p className="text-gray-500 text-xs">{alert.message}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {alert.is_triggered && (
          <CheckCircle className="h-4 w-4 text-green-400" />
        )}
        <span className="text-gray-600 text-xs">
          {formatDate(alert.created_at)}
        </span>
        <button
          onClick={() => onDelete(alert.id)}
          className="text-gray-600 hover:text-red-400 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}