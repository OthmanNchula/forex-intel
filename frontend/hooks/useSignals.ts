import { useState, useEffect } from "react";
import { analysisApi } from "@/lib/api";
import { Signal } from "@/types";

export function useSignals() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadSignals() {
    setLoading(true);
    try {
      const res = await analysisApi.getSignals();
      setSignals(res.data || []);
    } catch {
      setError("Failed to load signals.");
    } finally {
      setLoading(false);
    }
  }

  async function generateSignal(pair: string, timeframe: string) {
    const res = await analysisApi.generateSignal(pair, timeframe);
    const newSignal = res.data;
    setSignals((prev) => [newSignal, ...prev]);
    return newSignal;
  }

  useEffect(() => {
    loadSignals();
  }, []);

  return { signals, loading, error, loadSignals, generateSignal };
}