"use client";
import { useStore } from "@/store/useStore";
import { User } from "lucide-react";

export default function Header() {
  const { user, activePair, prices, marketOpen } = useStore();
  const currentPrice = prices[activePair];

  return (
    <header className="fixed top-14 md:top-0 left-0 md:left-56 right-0 h-14 bg-gray-900/70 backdrop-blur-md border-b border-white/[0.06] flex items-center justify-between px-4 z-40">
      {/* Active pair price */}
      <div className="flex items-center gap-2.5">
        <span
          className={`h-1.5 w-1.5 rounded-full shrink-0 ${
            marketOpen === false ? "bg-gray-500" : "bg-green-400 animate-pulse"
          }`}
          title={marketOpen === false ? "Market closed" : "Market open"}
        />
        <span className="text-gray-400 text-sm font-medium">{activePair}</span>
        {currentPrice && (
          <span className="text-white font-mono font-semibold tabular-nums">
            {currentPrice.toFixed(5)}
          </span>
        )}
        {marketOpen === false && (
          <span className="text-[11px] text-gray-500 hidden sm:inline">market closed</span>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        {user && (
          <span className="text-sm text-gray-300 hidden sm:block font-mono tabular-nums">
            ${user.account_balance.toLocaleString()}
          </span>
        )}
        <div className="flex items-center gap-2 bg-white/[0.05] ring-1 ring-white/[0.06] rounded-full px-3 py-1.5 transition-colors hover:bg-white/[0.08]">
          <div className="h-5 w-5 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0">
            <User className="h-3 w-3 text-white" />
          </div>
          <span className="text-sm text-white hidden sm:block">
            {user?.display_name || "Trader"}
          </span>
        </div>
      </div>
    </header>
  );
}