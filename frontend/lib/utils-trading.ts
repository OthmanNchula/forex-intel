// Format price based on pair type
export function formatPrice(price: number, pair: string): string {
  if (!price) return "0.00000";
  const p = pair.toUpperCase();
  if (p.includes("JPY")) return price.toFixed(3);
  if (p.includes("XAU")) return price.toFixed(2);
  return price.toFixed(5);
}

// Format pips
export function formatPips(pips: number): string {
  return `${pips.toFixed(1)} pips`;
}

// Format PnL with color class
export function getPnLColor(pnl: number): string {
  if (pnl > 0) return "text-green-400";
  if (pnl < 0) return "text-red-400";
  return "text-gray-400";
}

// Get direction color
export function getDirectionColor(direction: string): string {
  if (direction === "BUY") return "text-green-400";
  if (direction === "SELL") return "text-red-400";
  return "text-gray-400";
}

// Get direction background color
export function getDirectionBg(direction: string): string {
  if (direction === "BUY") return "bg-green-500/20 text-green-400 border-green-500/30";
  if (direction === "SELL") return "bg-red-500/20 text-red-400 border-red-500/30";
  return "bg-gray-500/20 text-gray-400 border-gray-500/30";
}

// Get confidence label and color
export function getConfidenceLabel(score: number): {
  label: string;
  color: string;
} {
  if (score >= 80) return { label: "High Confidence", color: "text-green-400" };
  if (score >= 60) return { label: "Moderate", color: "text-yellow-400" };
  if (score >= 40) return { label: "Low Confidence", color: "text-orange-400" };
  return { label: "Very Low", color: "text-red-400" };
}

// Get result badge color
export function getResultColor(result: string): string {
  if (result === "WIN") return "bg-green-500/20 text-green-400 border-green-500/30";
  if (result === "LOSS") return "bg-red-500/20 text-red-400 border-red-500/30";
  if (result === "OPEN") return "bg-blue-500/20 text-blue-400 border-blue-500/30";
  return "bg-gray-500/20 text-gray-400 border-gray-500/30";
}

// Format currency
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(amount);
}

// Format date
export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Get RSI label
export function getRSILabel(rsi: number): { label: string; color: string } {
  if (rsi >= 70) return { label: "Overbought", color: "text-red-400" };
  if (rsi <= 30) return { label: "Oversold", color: "text-green-400" };
  return { label: "Neutral", color: "text-gray-400" };
}

// Get trend color
export function getTrendColor(trend: string): string {
  if (trend === "BULLISH") return "text-green-400";
  if (trend === "BEARISH") return "text-red-400";
  return "text-gray-400";
}