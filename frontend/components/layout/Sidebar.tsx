"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  LineChart,
  Zap,
  Calculator,
  BookOpen,
  FlaskConical,
  Bell,
  Settings,
  TrendingUp,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { clearAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useState } from "react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/market", label: "Market Chart", icon: LineChart },
  { href: "/signals", label: "AI Signals", icon: Zap },
  { href: "/risk-calculator", label: "Risk Calc", icon: Calculator },
  { href: "/journal", label: "Journal", icon: BookOpen },
  { href: "/backtesting", label: "Backtesting", icon: FlaskConical },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  function handleNavClick() {
    setMobileOpen(false);
  }

  return (
    <>
      {/* Mobile top bar */}
      <div className="fixed top-0 left-0 right-0 h-14 bg-gray-900/80 backdrop-blur-md border-b border-white/[0.06] flex items-center justify-between px-4 z-50 md:hidden">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <TrendingUp className="h-4 w-4 text-white" />
          </div>
          <span className="text-white font-bold">Forex Intel</span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="text-gray-400 hover:text-white transition-colors"
        >
          {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden animate-in fade-in duration-200"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-screen bg-gray-900/80 backdrop-blur-md border-r border-white/[0.06] flex flex-col z-50 transition-all duration-300
          ${mobileOpen ? "w-56 translate-x-0" : "-translate-x-full"}
          md:translate-x-0 md:w-56
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-5 border-b border-white/[0.06]">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20 shrink-0">
            <TrendingUp className="h-4.5 w-4.5 text-white" />
          </div>
          <span className="text-white font-bold text-lg tracking-tight">Forex Intel</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                onClick={handleNavClick}
                className={`group relative flex items-center gap-3 px-4 py-2.5 mx-2 rounded-xl mb-1 transition-all duration-200 ${
                  active
                    ? "nav-active-pill text-blue-300 ring-1 ring-blue-500/25 shadow-[0_0_20px_-6px_rgba(59,130,246,0.5)]"
                    : "text-gray-400 hover:text-white hover:bg-white/[0.05]"
                }`}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-blue-400" />
                )}
                <Icon
                  className={`h-4.5 w-4.5 shrink-0 transition-transform duration-200 ${
                    active ? "" : "group-hover:scale-110 group-hover:-translate-y-px"
                  }`}
                />
                <span className="text-sm font-medium">{label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-2 border-t border-white/[0.06]">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-2.5 w-full rounded-xl text-gray-400 hover:text-red-400 hover:bg-red-400/10 transition-all duration-200"
          >
            <LogOut className="h-4.5 w-4.5 shrink-0" />
            <span className="text-sm font-medium">Logout</span>
          </button>
        </div>
      </aside>
    </>
  );
}