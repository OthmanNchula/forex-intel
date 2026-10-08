"""
Backtest the rules engine on historical candles — with and without the
sideways-market filter — so the thresholds can be judged by numbers.

Run from the backend folder (needs TWELVE_DATA_API_KEY in the environment
or in .env):

    python backtest_rules.py                       # all pairs, H1, 3000 candles
    python backtest_rules.py --timeframe H4
    python backtest_rules.py --pairs EUR/USD GBP/USD --candles 4000
    python backtest_rules.py --csv my_candles.csv --pair EUR/USD   # offline

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
          "USD/CAD": 0.00015, "USD/JPY": 0.012, "XAU/USD": 0.30}


def simulate(df: pd.DataFrame, pair: str, timeframe: str, htf_df, use_regime_filter: bool):
    """Walk forward through df; return a list of per-trade results in R."""
    spread = SPREAD.get(pair, 0.00012)
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


async def load_pair(pair: str, timeframe: str, candles: int):
    from app.services.market_data import fetch_ohlcv
    df = await fetch_ohlcv(pair, timeframe, candles)
    return df


def prep(df, timeframe):
    """Drop the still-forming last candle."""
    if df is None or len(df) < 2:
        return df
    return df.iloc[:-1]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="*", default=["EUR/USD", "GBP/USD", "USD/JPY",
                                                    "XAU/USD", "AUD/USD", "USD/CAD"])
    ap.add_argument("--timeframe", default="H1", choices=["M15", "H1", "H4"])
    ap.add_argument("--candles", type=int, default=3000)
    ap.add_argument("--csv", help="offline mode: CSV with datetime,open,high,low,close")
    ap.add_argument("--pair", default="EUR/USD", help="pair name to use with --csv")
    args = ap.parse_args()

    rows = []
    all_on, all_off = [], []

    jobs = []
    if args.csv:
        df = pd.read_csv(args.csv, parse_dates=["datetime"]).set_index("datetime").sort_index()
        jobs.append((args.pair, df, None))
    else:
        for pair in args.pairs:
            df = prep(await load_pair(pair, args.timeframe, args.candles), args.timeframe)
            htf = None
            if args.timeframe in HIGHER_TF:
                htf_n = max(200, args.candles * TF_MINUTES[args.timeframe] // TF_MINUTES[HIGHER_TF[args.timeframe]] + 100)
                htf = prep(await load_pair(pair, HIGHER_TF[args.timeframe], min(htf_n, 5000)), None)
            jobs.append((pair, df, htf))
            await asyncio.sleep(10)  # stay inside the data provider's rate limit

    for pair, df, htf in jobs:
        if df is None or len(df) < WARMUP + 50:
            print(f"{pair}: not enough data, skipped")
            continue
        print(f"Backtesting {pair} {args.timeframe} on {len(df)} candles ...", flush=True)
        on = simulate(df, pair, args.timeframe, htf, True)
        off = simulate(df, pair, args.timeframe, htf, False)
        all_on += on
        all_off += off
        for label, res in (("filter ON ", on), ("filter OFF", off)):
            s = summarize(res)
            rows.append((pair, label, s))

    print()
    print(f"{'pair':8} {'mode':11} {'trades':>6} {'win%':>6} {'avg R':>7} {'total R':>8} {'max DD':>7}")
    for pair, label, s in rows:
        print(f"{pair:8} {label:11} {s['trades']:>6} {s['win%']:>6} {s['avg_R']:>7} {s['total_R']:>8} {s['max_DD_R']:>7}")
    print()
    for label, res in (("ALL, regime filter ON ", all_on), ("ALL, regime filter OFF", all_off)):
        s = summarize(res)
        print(f"{label}: {s['trades']} trades, win {s['win%']}%, avg {s['avg_R']}R, "
              f"total {s['total_R']}R, worst drawdown {s['max_DD_R']}R")
    print("\nBreak-even win rate for a 2:1 trade is about 33%; costs push it slightly higher.")


if __name__ == "__main__":
    asyncio.run(main())
