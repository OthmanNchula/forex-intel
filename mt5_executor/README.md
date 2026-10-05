# Forex Intel — MT5 auto-execution bridge

Runs on a Windows machine (VPS recommended for 24/5 uptime) with the Exness
MT5 terminal installed. Polls the Forex Intel backend for signals that
clear the auto-execution bar and places them directly into MT5.

## 1. One-time setup on the Windows VPS

1. Install MT5 and log into your **Exness DEMO account** first (File > Open
   an Account, or download the Exness MT5 terminal directly and log in with
   your demo credentials).
2. In the terminal: **Tools > Options > Expert Advisors** — tick
   "Allow algorithmic trading" (this is what lets an external program like
   this one send orders; without it every `order_send` will be rejected).
3. Install Python 3.10+ if not already present.
4. In this folder:
   ```
   pip install -r requirements.txt
   copy .env.example .env
   ```
5. Edit `.env`:
   - `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` — your **demo** account's
     details (shown in MT5 under the account, or in your Exness Personal
     Area).
   - `BACKEND_URL` — `https://forex-intel-production.up.railway.app`
   - `EXECUTOR_API_KEY` — make up a long random string, then set the exact
     same value as `EXECUTOR_API_KEY` in the Railway backend's environment
     variables (Railway dashboard → your service → Variables). The backend
     refuses the executable-signals endpoints entirely until this is set.
   - `MT5_SYMBOL_SUFFIX` — open Market Watch in MT5 and check how your
     pairs are actually named. If you see "EURUSD" with no suffix, leave
     this blank. If you see something like "EURUSDm", set it to `m`.
   - Leave `IS_DEMO=true` and the risk/safety defaults as-is to start.
6. Run it:
   ```
   python executor.py
   ```
   You should see a "Connected to MT5" line with your demo account number
   and balance. Leave it running and watch `executor.log` for activity.

## 2. Backend changes this depends on

Already made in this codebase (see the main repo's commit for this
feature): a new `EXECUTOR_API_KEY` setting, and two new endpoints —
`GET /api/analysis/signals/executable` and
`POST /api/analysis/signals/{id}/mark-executed` — both guarded by that key,
not by a user login.

**Before this works, two things need to happen on Railway:**
1. Set `EXECUTOR_API_KEY` as an environment variable on the backend
   service, matching this `.env`.
2. The `signals` table needs 6 new columns the code now expects
   (`auto_executed`, `auto_executed_at`, `mt5_ticket`, `execution_price`,
   `execution_lot_size`, `execution_note`). This project doesn't use
   Alembic migrations — tables are created once with `create_all`, which
   does NOT add columns to a table that already exists. Run this once
   against the Railway Postgres database (Railway dashboard → Postgres →
   Data → Query, or `psql` with the connection string from Variables):
   ```sql
   ALTER TABLE signals ADD COLUMN IF NOT EXISTS auto_executed BOOLEAN DEFAULT FALSE;
   ALTER TABLE signals ADD COLUMN IF NOT EXISTS auto_executed_at TIMESTAMPTZ;
   ALTER TABLE signals ADD COLUMN IF NOT EXISTS mt5_ticket VARCHAR(50);
   ALTER TABLE signals ADD COLUMN IF NOT EXISTS execution_price DOUBLE PRECISION;
   ALTER TABLE signals ADD COLUMN IF NOT EXISTS execution_lot_size DOUBLE PRECISION;
   ALTER TABLE signals ADD COLUMN IF NOT EXISTS execution_note TEXT;
   CREATE INDEX IF NOT EXISTS ix_signals_auto_executed ON signals (auto_executed);
   ```

## 3. How it decides what to trade

- Only pulls signals where `confidence_score >= 65`, `rr_ratio >= 1.5`,
  `is_active = true`, and not already handled. This is already stricter
  than the bar for sending you a notification (62% / 1.5) — nothing
  double-checks an auto-executed trade before the money moves, so the bar
  is higher.
- Right before placing the order, re-checks the entry zone against a
  **live MT5 tick** (not the backend's own, slightly older check) — the
  exact problem you ran into with the SELL XAU/USD signal where price had
  already run through the whole entry zone by the time you read the
  email. If price has already blown through, the trade is skipped, not
  forced.
- Position size: `account balance × RISK_PCT_PER_TRADE%`, divided by the
  signal's own stop-loss distance in pips — the same math already used for
  the Risk Amount field in your Journal, so sizing here matches what the
  app already shows you.
- Take-profit used is `take_profit_2` (the signal's middle target) — this
  matches the R:R figure the backend verifies and shows you (see the fix
  to `ai_analysis.py` in the main repo).
- **Max concurrent trades**, **daily loss limit**, and **max consecutive
  losses** are all read live from MT5's own account/position/history data
  — no separate bookkeeping on this side that could drift from reality.
- Every signal the executor looks at — filled OR skipped — is reported
  back to the backend via `mark-executed`, so nothing is ever evaluated
  twice. `execution_note` on the signal in the database (and
  `executor.log` here) always says what happened and why.

## 4. Known simplifications (read before relying on this)

- **Skipped ≠ queued.** If a signal is skipped (stale entry, max
  concurrent trades, circuit breaker tripped), it is marked handled and
  will NOT be retried later even if the condition clears — it's just
  gone. This matches the pattern already in `auto_signal_engine.py`,
  but means a signal can be lost rather than delayed.
- **One VPS per account.** This script assumes a single MT5 terminal
  session; it is not designed to run against multiple accounts at once.
- **No partial fills / requotes handling beyond a single retry-free
  order_send.** A rejected order (e.g. "Invalid price" on a fast market)
  is logged and skipped, not retried.
- **Demo first, for real.** Nothing here has been run against a live
  account. Run it against the demo account for the 2-4 weeks you already
  planned, compare its fills against what you'd have taken manually, and
  only then consider pointing `.env` at live credentials (and flipping
  `IS_DEMO=false`, which only affects logging/labels, not behavior).

## 5. Keeping it running unattended

For actual 24/5 operation on a VPS, don't just leave a terminal window
open — use **Task Scheduler** to run `python executor.py` on startup and
auto-restart on crash, or install it as a Windows service with something
like [NSSM](https://nssm.cc/). Either way, make sure the MT5 terminal
itself is also set to launch and log in automatically on VPS reboot
(MT5 remembers the last login by default).
