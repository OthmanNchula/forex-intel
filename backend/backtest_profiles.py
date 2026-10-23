"""
Find and verify a profile for each pair/timeframe — honestly.

For every pair and timeframe:
  1. Split the history: the first 2/3 is the TRAINING part, the last 1/3
     is the TEST part (recent data the choice never sees).
  2. Try a small set of candidate profiles on the TRAINING part only:
     the current live rules (baseline), the designed profile from
     pair_profiles.DESIGNED_PROFILES, and a few alternatives
     (trend / range / both, stop 1.5 or 2.0 ATR, designed sessions or all).
  3. Pick the candidate with the best average R on TRAINING.
  4. Check that winner on the TEST part. It is APPROVED only if it is
     positive on both parts, with enough trades on the test part.
  5. Approved profiles are written to app/pair_profiles.json. Commit that
     file and set USE_PAIR_PROFILES=true on Railway to trade them.

Run from the backend folder (needs TWELVE_DATA_API_KEY):

    python backtest_profiles.py                              # all 6 pairs, H1 and H4
    python backtest_profiles.py --pairs EUR/USD AUD/USD
    python backtest_profiles.py --dry-run                    # do not write the JSON

Trades are simulated like backtest_rules.py: signal on a CLOSED candle,
entry at the NEXT candle's open, stop wins if a candle touches both,
spread charged, max 48 candles held, one trade at a time.
Results are in R: +2R is a full win, -1R a full loss.

Past results do not guarantee future results.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.indicator_engine import compute_all_indicators, calculate_ema  # noqa: E402
from app.services import pair_profiles  # noqa: E402
from backtest_rules import default_spread, summarize, TD_INTERVAL, prep  # noqa: E402

TF_MINUTES = {"H1": 60, "H4": 240}
HIGHER_TF = {"H1": "H4"}
MAX_HOLD = 48
WARMUP = 120
TRAIN_SHARE = 2 / 3

MIN_TRAIN_TRADES = 15      # a candidate needs this many training trades to be picked
MIN_TEST_TRADES = 8        # the winner needs this many test trades to be approved
MIN_TEST_AVG_R = 0.10      # ...and at least this average R on the test part

ALL_PAIRS = list(pair_profiles.DESIGNED_PROFILES.keys())


# ------------------------------------------------------------------ data
async def load_utc(pair: str, timeframe: str, candles: int):
    """Twelve Data candles in UTC (sessions depend on the real hour), cached per day."""
    import httpx
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_data")
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f"{pair.replace('/', '')}_{timeframe}_{candles}_utc_"
                                    f"{datetime.now():%Y%m%d}.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache, parse_dates=["datetime"]).set_index("datetime").sort_index()

    api_key = os.getenv("TWELVE_DATA_API_KEY", "").strip()
    if not api_key:
        sys.exit("Set TWELVE_DATA_API_KEY first, e.g.  $env:TWELVE_DATA_API_KEY='your-key'")
    params = {"symbol": pair, "interval": TD_INTERVAL[timeframe], "outputsize": min(candles, 5000),
              "apikey": api_key, "format": "JSON", "timezone": "UTC"}
    for _ in range(4):
        try:
            data = httpx.get("https://api.twelvedata.com/time_series", params=params, timeout=90).json()
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
            df = df.dropna(subset=["open", "high", "low", "close"])[["open", "high", "low", "close"]]
            df.to_csv(cache)
            await asyncio.sleep(8)          # stay inside ~8 requests/minute
            return df
        msg = str(data.get("message", "unknown error"))
        print(f"  {pair} {timeframe}: Twelve Data said: {msg[:120]}")
        if data.get("code") == 429 or "limit" in msg.lower() or "credits" in msg.lower():
            print("  waiting 65s for the rate limit to reset...")
            await asyncio.sleep(65)
            continue
        return None
    return None


# ------------------------------------------------------------ precompute
def precompute(df: pd.DataFrame, timeframe: str, htf_df):
    """Indicators for every closed candle (computed once, reused by every candidate)."""
    tf_delta = pd.Timedelta(minutes=TF_MINUTES[timeframe])
    htf_close_times = htf_state = None
    if htf_df is not None and timeframe in HIGHER_TF and len(htf_df) > 60:
        e20 = calculate_ema(htf_df["close"], 20)
        e50 = calculate_ema(htf_df["close"], 50)
        htf_close_times = (htf_df.index + pd.Timedelta(minutes=TF_MINUTES[HIGHER_TF[timeframe]])).values
        htf_state = np.where(e20.values > e50.values, "ABOVE", "BELOW")

    inds, htfs, closes = [None] * len(df), [None] * len(df), [None] * len(df)
    for i in range(WARMUP, len(df) - 2):
        ind = compute_all_indicators(df.iloc[max(0, i - 199): i + 1], include_chart=False)
        if not ind:
            continue
        ind.pop("chart_data", None)
        inds[i] = ind
        close_time = df.index[i] + tf_delta
        closes[i] = close_time.to_pydatetime().replace(tzinfo=timezone.utc)
        if htf_close_times is not None:
            pos = np.searchsorted(htf_close_times, close_time.to_datetime64(), side="right") - 1
            if pos >= 0:
                htfs[i] = str(htf_state[pos])
    return inds, htfs, closes


# -------------------------------------------------------------- simulate
def simulate(df, pre, pair, timeframe, profile, start, end):
    """Trades whose signal candle is in [start, end)."""
    inds, htfs, closes = pre
    opens, highs, lows, cl = (df[c].values for c in ("open", "high", "low", "close"))
    n = len(df)
    spread = default_spread(pair)
    results = []
    i = start
    while i < min(end, n - 2):
        ind = inds[i]
        if ind is None:
            i += 1
            continue
        d = pair_profiles.evaluate_with_profile(pair, timeframe, ind, htfs[i], profile, closes[i])
        if d["action"] != "TRADE":
            i += 1
            continue
        sig = d["signal"]
        sign = 1 if sig["direction"] == "BUY" else -1
        risk = abs(sig["current_price"] - sig["stop_loss"])
        reward = abs(sig["take_profit_2"] - sig["current_price"])
        if risk <= 0:
            i += 1
            continue
        entry = opens[i + 1]
        stop, target = entry - sign * risk, entry + sign * reward
        outcome, exit_i = None, None
        last = min(i + 1 + MAX_HOLD, n - 1)
        for j in range(i + 1, last + 1):
            if (lows[j] <= stop) if sign == 1 else (highs[j] >= stop):
                outcome, exit_i = -1.0, j
                break
            if (highs[j] >= target) if sign == 1 else (lows[j] <= target):
                outcome, exit_i = reward / risk, j
                break
        if outcome is None:
            exit_i = last
            outcome = sign * (cl[last] - entry) / risk
        outcome -= spread / risk
        results.append({"time": df.index[i], "r": outcome, "playbook": d.get("playbook", "trend"),
                        "pattern": d.get("pattern")})
        i = exit_i + 1
    return results


# ------------------------------------------------------------ candidates
def candidates(pair, timeframe):
    designed = pair_profiles.DESIGNED_PROFILES.get(pair, {}).get(timeframe, pair_profiles.BASELINE)
    out = {"baseline (live rules)": dict(pair_profiles.BASELINE),
           "designed": dict(designed)}
    sess_options = [None] if not designed.get("sessions") else [designed["sessions"], None]
    for sess in sess_options:
        tag = "designed sessions" if sess else "all hours"
        for sl in (1.5, 2.0):
            out[f"trend, stop {sl}, {tag}"] = {"playbooks": ["trend"], "sl_atr": sl, "sessions": sess}
            out[f"trend+range, stop {sl}, {tag}"] = {"playbooks": ["trend", "range"], "sl_atr": sl,
                                                    "sessions": sess}
        out[f"range, {tag}"] = {"playbooks": ["range"], "sl_atr": 1.5, "sessions": sess}
    # drop exact duplicates, keeping the first (more meaningful) name
    seen, unique = set(), {}
    for name, prof in out.items():
        key = json.dumps(prof, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique[name] = prof
    return unique


def fmt(s):
    return f"{s['avg_R']:+.3f}R x{s['trades']}" if s["trades"] else "no trades"


# ------------------------------------------------------------------ main
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="*", default=ALL_PAIRS)
    ap.add_argument("--timeframe", nargs="+", default=["H1", "H4"], choices=["H1", "H4"])
    ap.add_argument("--candles", type=int, default=5000)
    ap.add_argument("--dry-run", action="store_true", help="print results only, do not write the JSON")
    args = ap.parse_args()
    pairs = [p.upper() for p in args.pairs]

    approved, report = {}, []
    for pair in pairs:
        h4 = prep(await load_utc(pair, "H4", args.candles), "H4")
        for tf in args.timeframe:
            df = h4 if tf == "H4" else prep(await load_utc(pair, tf, args.candles), tf)
            if df is None or len(df) < WARMUP + 300:
                print(f"{pair} {tf}: not enough data, skipped")
                continue
            print(f"\n{pair} {tf}: preparing {len(df)} candles "
                  f"({df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}) ...", flush=True)
            pre = precompute(df, tf, h4 if tf == "H1" else None)
            cut = WARMUP + int((len(df) - WARMUP) * TRAIN_SHARE)
            print(f"  training: up to {df.index[cut]:%Y-%m-%d}   test: after that")

            rows = []
            for name, prof in candidates(pair, tf).items():
                train = summarize(simulate(df, pre, pair, tf, prof, WARMUP, cut))
                rows.append((name, prof, train))
                print(f"  {name:38} training {fmt(train)}")

            eligible = [r for r in rows if r[2]["trades"] >= MIN_TRAIN_TRADES]
            base = rows[0]
            base_test = summarize(simulate(df, pre, pair, tf, base[1], cut, len(df)))
            if not eligible:
                verdict, best, test = "OFF — too few trades to judge", None, None
            else:
                best = max(eligible, key=lambda r: r[2]["avg_R"])
                test = summarize(simulate(df, pre, pair, tf, best[1], cut, len(df)))
                ok = (best[2]["avg_R"] > 0 and test["trades"] >= MIN_TEST_TRADES
                      and test["avg_R"] >= MIN_TEST_AVG_R)
                verdict = "APPROVED" if ok else "OFF — failed on unseen test data"
                if ok:
                    approved.setdefault(pair, {})[tf] = {
                        **best[1], "chosen": best[0],
                        "train": {k: best[2][k] for k in ("trades", "win%", "avg_R", "max_DD_R")},
                        "test": {k: test[k] for k in ("trades", "win%", "avg_R", "max_DD_R")},
                    }
            report.append((pair, tf, best, test, base_test, verdict))
            print(f"  -> picked: {best[0] if best else '-'} | test {fmt(test) if test else '-'} "
                  f"| live rules on test {fmt(base_test)} | {verdict}")

    print("\n" + "=" * 100)
    print(f"{'pair':8} {'tf':3} {'chosen profile':38} {'training':>14} {'TEST':>14} "
          f"{'live rules TEST':>16}  verdict")
    for pair, tf, best, test, base_test, verdict in report:
        print(f"{pair:8} {tf:3} {(best[0] if best else '-'):38} "
              f"{(fmt(best[2]) if best else '-'):>14} {(fmt(test) if test else '-'):>14} "
              f"{fmt(base_test):>16}  {verdict}")

    print("\nThe TEST column is the honest number: data the choice never saw.")
    print(f"Approval needs: positive training, >= {MIN_TEST_TRADES} test trades, "
          f"test avg >= {MIN_TEST_AVG_R:+.2f}R.")

    if args.dry_run:
        print("\n--dry-run: app/pair_profiles.json not written.")
        return
    payload = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "note": "Written by backtest_profiles.py. Only approved pair/timeframes are listed; "
                "only these trade when USE_PAIR_PROFILES=true.",
        "profiles": approved,
    }
    with open(pair_profiles.PROFILES_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    n = sum(len(v) for v in approved.values())
    print(f"\nWrote {n} approved pair/timeframe profile(s) to app/pair_profiles.json")
    print("Past results do not guarantee future results.")


if __name__ == "__main__":
    asyncio.run(main())
