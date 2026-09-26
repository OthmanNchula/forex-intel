// User types
export interface User {
  id: string;
  email: string;
  display_name: string;
  account_balance: number;
  risk_per_trade_pct: number;
  max_daily_risk_pct: number;
  preferred_pairs: string[];
  timezone: string;
  is_demo: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// Signal types
export interface Signal {
  id: string;
  pair: string;
  timeframe: string;
  direction: "BUY" | "SELL" | "NO_TRADE";
  current_price: number;
  entry_low: number | null;
  entry_high: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  take_profit_3: number | null;
  rr_ratio: number | null;
  confidence_score: number | null;
  ai_explanation: string | null;
  risk_warning: string | null;
  ema20: number | null;
  ema50: number | null;
  rsi: number | null;
  macd_hist: number | null;
  atr: number | null;
  is_active: boolean;
  created_at: string;
}

// Trade types
export interface Trade {
  id: string;
  user_id: string;
  pair: string;
  direction: "BUY" | "SELL";
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  lot_size: number;
  risk_amount: number;
  result: "OPEN" | "WIN" | "LOSS" | "BREAKEVEN";
  close_price: number | null;
  pnl: number | null;
  pnl_pips: number | null;
  opened_at: string;
  closed_at: string | null;
  ai_reason: string | null;
  user_notes: string | null;
  screenshot_url: string | null;
}

export interface TradeStats {
  total_trades: number;
  open_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_rr: number;
}

// Risk calculator types
export interface RiskCalculationResult {
  pair: string;
  account_balance: number;
  risk_pct: number;
}

export interface RiskCalculationResult {
  pair: string;
  account_balance: number;
  risk_pct: number;
  risk_amount: number;
  sl_pips: number;
  lot_size: number;
  pip_value: number;
  max_loss: number;
  potential_profit: number;
  rr_ratio: number;
  warnings: string[];
  daily_risk_used: number;
  daily_risk_limit: number;
  daily_risk_remaining: number;
}

export interface ChartDataPoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  ema20: number;
  ema50: number;
  rsi: number;
  macd_hist: number;
  atr: number;
}

export interface Indicators {
  current_price: number;
  ema20: number;
  ema50: number;
  ema_cross: string;
  ema20_slope: number;
  ema50_slope: number;
  rsi: number;
  macd_hist: number;
  atr: number;
  trend: string;
  volatility: string;
  nearest_support: number | null;
  nearest_resistance: number | null;
  support_levels: number[];
  resistance_levels: number[];
  chart_data: ChartDataPoint[];
}

export interface Alert {
  id: string;
  pair: string;
  alert_type: string;
  condition_value: number | null;
  message: string | null;
  is_triggered: boolean;
  triggered_at: string | null;
  created_at: string;
}