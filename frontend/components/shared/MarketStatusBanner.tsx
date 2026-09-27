"use client";
import { useStore } from "@/store/useStore";

/**
 * Real-time "market closed" banner, driven by the "market_status"
 * messages pushed over the /ws/prices socket (see useLivePrice.ts and
 * backend/app/websocket/price_feed.py). The backend re-broadcasts this
 * every ~60s and immediately on connect, so this banner appears and
 * disappears live — no page refresh needed for it to show up when the
 * weekend close hits or clear when the market reopens.
 *
 * Renders nothing while marketOpen is null (status not received yet)
 * or true (market open) — only shown when we know for certain the
 * market is closed.
 */
export default function MarketStatusBanner() {
  const { marketOpen } = useStore();

  if (marketOpen !== false) return null;

  return (
    <div className="w-full bg-slate-500/[0.08] ring-1 ring-slate-400/20 rounded-xl px-4 py-2.5 text-center backdrop-blur-sm">
      <p className="text-slate-300 text-xs font-medium">
        <span className="h-1.5 w-1.5 rounded-full bg-slate-400 inline-block mr-1.5 align-middle" />
        Forex market is currently <strong className="text-slate-100">closed</strong>. New AI
        signals resume when trading reopens — existing signals and your journal are unaffected.
      </p>
    </div>
  );
}
