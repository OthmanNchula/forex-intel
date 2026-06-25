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
      <div className="fixed top-0 left-0 right-0 h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4 z-50 md:hidden">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-yellow-400" />
          <span className="text-white font-bold">Forex Intel</span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="text-gray-400 hover:text-white"
        >
          {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-screen bg-gray-900 border-r border-gray-800 flex flex-col z-50 transition-all duration-300
          ${mobileOpen ? "w-56 translate-x-0" : "-translate-x-full"}
          md:translate-x-0 md:w-56
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-800">
          <TrendingUp className="h-6 w-6 text-yellow-400 shrink-0" />
          <span className="text-white font-bold text-lg">Forex Intel</span>
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
                className={`flex items-center gap-3 px-4 py-3 mx-2 rounded-lg mb-1 transition-colors ${
                  active
                    ? "bg-blue-600/20 text-blue-400 border border-blue-600/30"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span className="text-sm font-medium">{label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-2 border-t border-gray-800">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-400/10 transition-colors"
          >
            <LogOut className="h-5 w-5 shrink-0" />
            <span className="text-sm font-medium">Logout</span>
          </button>
        </div>
      </aside>
    </>
  );
}