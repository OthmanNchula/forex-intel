"""
Backtest the rules engine on historical candles — with and without the
sideways-market filter — so the thresholds can be judged by numbers.

Run from the backend folder (needs TWELVE_DATA_API_KEY in the environment
or in .env):

    python backtest_rules.py                       # 8 NEW candidate pairs, H1 and H4
    python backtest_rules.py --pairs EUR/USD GBP/USD --timeframe H4
    python backtest_rules.py --pairs all           # every pair listed in SPREAD below
    python backtest_rules.py --csv my_candles.csv --pair EUR/USD   # offline

Downloaded candles are saved in backtest_data/ and reused on later runs the
same day, so a re-run does not spend Twelve Data credits again.

How trades are simulated (deliberately conservative):
  * A signal is read from a CLOSED candle; the trade enters at the NEXT
    candle's open (that is what live trading can actually get).
  * Stop = 1.5 x ATR, target = 3 x ATR (the same fixed 2:1 as live).
  * If one candle touches both stop and target, the stop is assumed to
    have been hit first.
  * A trade still open after MAX_HOLD candles is closed at that candle's close.
  * A spread cost is subtracted from every trade.
  * One trade at a time per pair/timeframe (like the live "active signal" rule).
Results are in R: +2R is a full win, -1R a full loss.

Past results do not guarantee future results. Treat this as a sanity
check on the rules, not a promise of profit.
"""
import argparse
import asyncio
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.indicator_engine import compute_all_indicators, calculate_ema  # noqa: E402
from app.services import rules_engine  # noqa: E402

TF_MINUTES = {"M15": 15, "H1": 60, "H4": 240}
HIGHER_TF = {"M15": "H1", "H1": "H4"}
MAX_HOLD = 48
WARMUP = 120

# Typical spread, in price units (1 pip = 0.0001, JPY 0.01, gold 0.1)
SPREAD = {"EUR/USD": 0.00010, "GBP/USD": 0.00013, "AUD/USD": 0.00012,
          "USD/CAD": 0.00015, "USD/JPY": 0.012, "XAU/USD": 0.30,
          # new candidates (typical retail spreads, a little on the cautious side)
          "NZD/USD": 0.00018, "USD/CHF": 0.00016, "EUR/GBP": 0.00015,
          "EUR/JPY": 0.018, "GBP/JPY": 0.028, "AUD/JPY": 0.020,
          "EUR/AUD": 0.00025, "GBP/AUD": 0.00035}
CURRENT_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD", "AUD/USD", "USD/CAD"]
NEW_PAIRS = ["NZD/USD", "USD/CHF", "EUR/GBP", "EUR/JPY", "GBP/JPY", "AUD/JPY", "EUR/AUD", "GBP/AUD"]
MIN_TRADES_FOR_VERDICT = 30


def default_spread(pair: str) -> float:
    if pair in SPREAD:
        return SPREAD[pair]
    return 0.02 if "JPY" in pair else 0.00020


def simulate(df: pd.DataFrame, pair: str, timeframe: str, htf_df, use_regime_filter: bool):
    """Walk forward through df; return a list of per-trade results in R."""
    spread = default_spread(pair)
    tf_delta = pd.Timedelta(minutes=TF_MINUTES[timeframe])

    # Higher-timeframe EMA state, available only once each HTF candle has CLOSED.
    htf_close_times, htf_state = None, None
    if htf_df is not None and len(htf_df) > 60:
        e20 = calculate_ema(htf_df["close"], 20)
        e50 = calculate_ema(htf_df["close"], 50)
        htf_delta = pd.Timedelta(minutes=TF_MINUTES[HIGHER_TF[timeframe]])
        htf_close_times = (htf_df.index + htf_delta).values
        htf_state = np.where(e20.values > e50.values, "ABOVE", "BELOW")

    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    index = df.index

    results = []
    i = WARMUP
    n = len(df)
    while i < n - 2:
        window = df.iloc[max(0, i - 199): i + 1]
        ind = compute_all_indicators(window, include_chart=False)
        if not ind:
            i += 1
            continue

        htf_cross = None
        if htf_close_times is not None:
            now_close = (index[i] + tf_delta).to_datetime64()
            pos = np.searchsorted(htf_close_times, now_close, side="right") - 1
            if pos >= 0:
                htf_cross = str(htf_state[pos])

        decision = rules_engine.evaluate(pair, timeframe, ind, htf_cross, use_regime_filter)
        if decision["action"] != "TRADE":
            i += 1
            continue

        sig = decision["signal"]
        direction = sig["direction"]
        atr = sig["atr"]
        entry = opens[i + 1]
        sign = 1 if direction == "BUY" else -1
        stop = entry - sign * atr * rules_engine.SL_ATR
        target = entry + sign * atr * rules_engine.TP2_ATR
        risk = atr * rules_engine.SL_ATR

        outcome_r, exit_i = None, None
        last = min(i + 1 + MAX_HOLD, n - 1)
        for j in range(i + 1, last + 1):
            hit_stop = lows[j] <= stop if sign == 1 else highs[j] >= stop
            hit_target = highs[j] >= target if sign == 1 else lows[j] <= target
            if hit_stop:                       # stop wins ties
                outcome_r, exit_i = -1.0, j
                break
            if hit_target:
                outcome_r, exit_i = rules_engine.FIXED_RR, j
                break
        if outcome_r is None:
            exit_i = last
            outcome_r = sign * (closes[last] - entry) / risk

        outcome_r -= spread / risk              # spread cost in R
        results.append({"time": index[i], "direction": direction,
                        "regime": decision["regime"], "score": decision["score"],
                        "r": outcome_r})
        i = exit_i + 1                          # one trade at a time
    return results


def summarize(results):
    if not results:
        return {"trades": 0, "win%": 0.0, "avg_R": 0.0, "total_R": 0.0, "max_DD_R": 0.0}
    r = np.array([t["r"] for t in results])
    equity = np.cumsum(r)
    peak = np.maximum.accumulate(equity)
    return {
        "trades": len(r),
        "win%": round(100 * float((r > 0).mean()), 1),
        "avg_R": round(float(r.mean()), 3),
        "total_R": round(float(r.sum()), 1),
        "max_DD_R": round(float((peak - equity).max()), 1),
    }


TD_INTERVAL = {"M15": "15min", "H1": "1h", "H4": "4h"}


async def load_pair(pair: str, timeframe: str, candles: int):
    """Download history straight from Twelve Data. Only needs the
    TWELVE_DATA_API_KEY environment variable — no database, Redis or app
    settings required. The key is never printed."""
    import httpx

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_data")
    os.makedirs(cache_dir, exist_ok=True)
    from datetime import date
    cache = os.path.join(cache_dir, f"{pair.replace('/', '')}_{timeframe}_{candles}_{date.today():%Y%m%d}.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache, parse_dates=["datetime"]).set_index("datetime").sort_index()

    api_key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not api_key:
        sys.exit("Set TWELVE_DATA_API_KEY first, e.g.  $env:TWELVE_DATA_API_KEY='your-key'")

    params = {"symbol": pair, "interval": TD_INTERVAL[timeframe],
              "outputsize": min(candles, 5000), "apikey": api_key, "format": "JSON"}
    for attempt in range(4):
        try:
            r = httpx.get("https://api.twelvedata.com/time_series", params=params, timeout=90)
            data = r.json()
        except Exception as e:
            print(f"  {pair} {timeframe}: request failed ({type(e).__name__}), retrying...")
            await asyncio.sleep(15)
            continue
        if "values" in data:
            df = pd.DataFrame(data["values"])
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime").sort_index()
            for col in ("open", "high", "low", "close"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["open", "high", "low", "close"])
            df[["open", "high", "low", "close"]].to_csv(cache)
            await asyncio.sleep(8)   # stay inside ~8 requests/minute
            return df
        msg = str(data.get("message", "unknown error"))
        print(f"  {pair} {timeframe}: Twelve Data said: {msg[:120]}")
        if data.get("code") == 429 or "limit" in msg.lower() or "credits" in msg.lower():
            print("  waiting 65s for the rate limit to reset...")
            await asyncio.sleep(65)
            continue
        return None
    return None


def prep(df, timeframe):
    """Drop the still-forming last candle."""
    if df is None or len(df) < 2:
        return df
    return df.iloc[:-1]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="*", default=None,
                    help="pairs to test; default = the 8 new candidates; 'all' = every known pair")
    ap.add_argument("--timeframe", nargs="+", default=["H1", "H4"], choices=["M15", "H1", "H4"])
    ap.add_argument("--candles", type=int, default=3000)
    ap.add_argument("--csv", help="offline mode: CSV with datetime,open,high,low,close")
    ap.add_argument("--pair", default="EUR/USD", help="pair name to use with --csv")
    args = ap.parse_args()

    if args.pairs is None:
        pairs = NEW_PAIRS
    elif [p.lower() for p in args.pairs] == ["all"]:
        pairs = CURRENT_PAIRS + NEW_PAIRS
    else:
        pairs = [p.upper() for p in args.pairs]

    rows = []                      # (pair, tf, mode, summary)
    totals = {}                    # (tf, mode) -> list of trades
    for tf in args.timeframe:
        jobs = []
        if args.csv:
            df = pd.read_csv(args.csv, parse_dates=["datetime"]).set_index("datetime").sort_index()
            jobs.append((args.pair, df, None))
        else:
            for pair in pairs:
                df = prep(await load_pair(pair, tf, args.candles), tf)
                htf = None
                if tf in HIGHER_TF:
                    htf_n = max(200, args.candles * TF_MINUTES[tf] // TF_MINUTES[HIGHER_TF[tf]] + 100)
                    htf = prep(await load_pair(pair, HIGHER_TF[tf], min(htf_n, 5000)), None)
                jobs.append((pair, df, htf))

        for pair, df, htf in jobs:
            if df is None or len(df) < WARMUP + 50:
                print(f"{pair} {tf}: not enough data, skipped")
                continue
            print(f"Backtesting {pair} {tf} on {len(df)} candles ...", flush=True)
            for label, flag in (("filter ON ", True), ("filter OFF", False)):
                res = simulate(df, pair, tf, htf, flag)
                rows.append((pair, tf, label, summarize(res)))
                totals.setdefault((tf, label), []).extend(res)

    print()
    print(f"{'pair':8} {'tf':3} {'mode':11} {'trades':>6} {'win%':>6} {'avg R':>7} {'total R':>8} {'max DD':>7}")
    for pair, tf, label, s in rows:
        print(f"{pair:8} {tf:3} {label:11} {s['trades']:>6} {s['win%']:>6} {s['avg_R']:>7} {s['total_R']:>8} {s['max_DD_R']:>7}")
    print()
    for (tf, label), res in totals.items():
        s = summarize(res)
        print(f"ALL {tf}, regime {label}: {s['trades']} trades, win {s['win%']}%, avg {s['avg_R']}R, "
              f"total {s['total_R']}R, worst drawdown {s['max_DD_R']}R")

    # Verdict per pair, using the live setting (regime filter ON)
    print("\nVERDICT (regime filter ON, as traded live):")
    by_pair = {}
    for pair, tf, label, s in rows:
        if label.strip() == "filter ON":
            by_pair.setdefault(pair, {})[tf] = s
    for pair, per_tf in by_pair.items():
        enough = all(s["trades"] >= MIN_TRADES_FOR_VERDICT for s in per_tf.values())
        positive = [tf for tf, s in per_tf.items() if s["avg_R"] > 0]
        detail = ", ".join(f"{tf} {s['avg_R']:+.3f}R x{s['trades']}" for tf, s in per_tf.items())
        if len(positive) == len(per_tf) and enough:
            verdict = "ADD   — positive on every timeframe tested"
        elif positive:
            verdict = "WATCH — positive on " + "/".join(positive) + " only"
        else:
            verdict = "SKIP  — negative"
        if not enough:
            verdict += f" (fewer than {MIN_TRADES_FOR_VERDICT} trades somewhere: low confidence)"
        print(f"  {pair:8} {verdict}   [{detail}]")
    print("\nBreak-even win rate for a 2:1 trade is about 33%; costs push it slightly higher.")
    print("Past results do not guarantee future results.")


if __name__ == "__main__":
    asyncio.run(main())
