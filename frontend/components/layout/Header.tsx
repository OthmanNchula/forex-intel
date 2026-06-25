"use client";
import { useStore } from "@/store/useStore";
import { User } from "lucide-react";

export default function Header() {
  const { user, activePair, prices } = useStore();
  const currentPrice = prices[activePair];

  return (
    <header className="fixed top-14 md:top-0 left-0 md:left-56 right-0 h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4 z-40">
      {/* Active pair price */}
      <div className="flex items-center gap-3">
        <span className="text-gray-400 text-sm">{activePair}</span>
        {currentPrice && (
          <span className="text-white font-mono font-semibold">
            {currentPrice.toFixed(5)}
          </span>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        {user?.is_demo && (
          <span className="text-xs bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-2 py-1 rounded-full">
            DEMO
          </span>
        )}
        {user && (
          <span className="text-sm text-gray-400 hidden sm:block">
            ${user.account_balance.toLocaleString()}
          </span>
        )}
        <div className="flex items-center gap-2 bg-gray-800 rounded-full px-3 py-1.5">
          <User className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-white hidden sm:block">
            {user?.display_name || "Trader"}
          </span>
        </div>
      </div>
    </header>
  );
}