import { useState, useEffect } from "react";
import { alertsApi } from "@/lib/api";
import { Alert } from "@/types";

export function useAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadAlerts() {
    setLoading(true);
    try {
      const res = await alertsApi.getAlerts();
      setAlerts(res.data.alerts || []);
      setNotifications(res.data.notifications || []);
    } catch (err) {
      console.error("Failed to load alerts:", err);
    } finally {
      setLoading(false);
    }
  }

  async function createAlert(data: {
    pair: string;
    alert_type: string;
    condition_value?: number;
    message?: string;
  }) {
    const res = await alertsApi.createAlert(data);
    setAlerts((prev) => [res.data, ...prev]);
    return res.data;
  }

  async function deleteAlert(id: string) {
    await alertsApi.deleteAlert(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  useEffect(() => {
    loadAlerts();
  }, []);

  return {
    alerts,
    notifications,
    loading,
    loadAlerts,
    createAlert,
    deleteAlert,
  };
}