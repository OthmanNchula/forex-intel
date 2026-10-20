"use client";

/**
 * "Export" button for the Trade Journal page.
 * Opens a small panel: optional date range + pair, then download as
 * Excel (.xlsx) or PDF. Files are built by the backend:
 *   GET /api/journal/export/excel   GET /api/journal/export/pdf
 */
import { useEffect, useRef, useState } from "react";
import { Download, FileSpreadsheet, FileText, Loader2, X } from "lucide-react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://forex-intel-production.up.railway.app";
const TOKEN_KEY = "forex_intel_token";
const PAIRS = ["", "EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD"];

type Format = "excel" | "pdf";

export default function ExportJournalButton() {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [pair, setPair] = useState("");
  const [busy, setBusy] = useState<Format | null>(null);
  const [error, setError] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);

  // close when clicking outside the panel
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  async function download(format: Format) {
    setError("");
    setBusy(format);
    try {
      const params = new URLSearchParams();
      if (start) params.set("start", start);
      if (end) params.set("end", end);
      if (pair) params.set("pair", pair);
      const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
      const res = await fetch(`${API_URL}/api/journal/export/${format}?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        throw new Error(res.status === 401 ? "Session expired — please log in again." : `Export failed (${res.status}).`);
      }
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || `forex_intel_journal.${format === "excel" ? "xlsx" : "pdf"}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed.");
    } finally {
      setBusy(null);
    }
  }

  const input =
    "w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-violet-500";

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-white hover:bg-white/10"
      >
        <Download className="h-4 w-4" />
        Export
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-2xl border border-white/10 bg-[#0d1220] p-4 shadow-2xl">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-semibold text-white">Export journal</span>
            <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-white" aria-label="Close">
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="mb-3 grid grid-cols-2 gap-2">
            <label className="text-xs text-gray-400">
              From
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={input} />
            </label>
            <label className="text-xs text-gray-400">
              To
              <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={input} />
            </label>
          </div>
          <label className="mb-4 block text-xs text-gray-400">
            Pair
            <select value={pair} onChange={(e) => setPair(e.target.value)} className={input}>
              {PAIRS.map((p) => (
                <option key={p || "all"} value={p} className="bg-[#0d1220]">
                  {p || "All pairs"}
                </option>
              ))}
            </select>
          </label>
          <p className="mb-3 text-xs text-gray-500">Leave dates empty to export every trade.</p>

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => download("excel")}
              disabled={busy !== null}
              className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-3 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
            >
              {busy === "excel" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="h-4 w-4" />}
              Excel
            </button>
            <button
              onClick={() => download("pdf")}
              disabled={busy !== null}
              className="flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-3 py-2.5 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-60"
            >
              {busy === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              PDF
            </button>
          </div>
          {error && <p className="mt-3 text-xs text-rose-400">{error}</p>}
        </div>
      )}
    </div>
  );
}
