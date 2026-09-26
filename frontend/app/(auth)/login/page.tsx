"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { TrendingUp, Eye, EyeOff } from "lucide-react";
import { authApi } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { useStore } from "@/store/useStore";

export default function LoginPage() {
  const router = useRouter();
  const { setUser, setToken } = useStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await authApi.login({ email, password });
      const { access_token, user } = res.data;
      saveAuth(access_token, user);
      setToken(access_token);
      setUser(user);
      router.push("/dashboard");
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Login failed. Check your credentials."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen app-shell-bg flex items-center justify-center p-4">
      <div className="w-full max-w-md animate-in fade-in zoom-in-95 duration-500">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
            <TrendingUp className="h-5 w-5 text-white" />
          </div>
          <span className="text-2xl font-bold text-white tracking-tight">Forex Intel</span>
        </div>

        {/* Card */}
        <div className="glass-card p-8">
          <h1 className="text-xl font-bold text-white mb-2">Welcome back</h1>
          <p className="text-gray-400 text-sm mb-6">
            Sign in to your trading dashboard
          </p>

          {error && (
            <div className="bg-red-500/10 ring-1 ring-red-500/30 rounded-xl p-3 mb-4">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] rounded-xl px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-blue-500/50 transition-shadow"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full bg-white/[0.05] ring-1 ring-white/[0.1] rounded-xl px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-blue-500/50 transition-shadow pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 rounded-xl transition-all duration-200 shadow-lg shadow-blue-600/20"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>

          <p className="text-center text-gray-400 text-sm mt-6">
            Don't have an account?{" "}
            <Link href="/register" className="text-blue-400 hover:text-blue-300 transition-colors">
              Create one
            </Link>
          </p>
        </div>

        {/* Disclaimer */}
        <p className="text-center text-gray-600 text-xs mt-6">
          ⚠️ Not financial advice. Always use a demo account first.
        </p>
      </div>
    </div>
  );
}