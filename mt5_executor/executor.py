"""
Forex Intel — MT5 auto-execution bridge.

Runs on a Windows machine/VPS with the Exness MT5 terminal installed and
logged in ("Algo Trading" enabled). Polls the Forex Intel backend for
signals that clear the auto-execution bar, re-checks each one is still
fresh against a LIVE MT5 tick (not the backend's own already-somewhat-
stale check), sizes the position by fixed % account risk, and places a
market order with the signal's own stop-loss and take-profit.

This is the last line of defense before real money moves — every check
here fails CLOSED (skips the trade) rather than open, because a missed
trade costs nothing and a bad one costs real money.

Usage:
    pip install -r requirements.txt
    copy .env.example .env   &&   edit .env with your DEMO account first
    python executor.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 package not found. On Windows: pip install MetaTrader5")
    sys.exit(1)

load_dotenv()

# --- Config ---------------------------------------------------------------

MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")
MT5_TERMINAL_PATH = os.getenv("MT5_TERMINAL_PATH", "").strip() or None

BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
EXECUTOR_API_KEY = os.getenv("EXECUTOR_API_KEY", "")

MT5_SYMBOL_SUFFIX = os.getenv("MT5_SYMBOL_SUFFIX", "")

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

RISK_PCT_PER_TRADE = float(os.getenv("RISK_PCT_PER_TRADE", "1.0"))
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "3"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3.0"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
SLIPPAGE_POINTS = int(os.getenv("SLIPPAGE_POINTS", "20"))
IS_DEMO = os.getenv("IS_DEMO", "true").strip().lower() != "false"

MAGIC_NUMBER = 20261003  # arbitrary, just has to be unique to this bot
STATE_FILE = Path(__file__).parent / "state.json"

# --- Logging ---------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / "executor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("executor")


# --- Daily circuit-breaker state --------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": None, "day_start_balance": None, "consecutive_losses": 0}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def today_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def refresh_daily_state(state: dict) -> dict:
    """Roll the circuit-breaker state over at each new UTC day."""
    today = today_utc_str()
    if state.get("date") != today:
        account = mt5.account_info()
        balance = account.balance if account else None
        log.info(f"New trading day ({today}) — resetting circuit breaker. Balance: {balance}")
        state = {"date": today, "day_start_balance": balance, "consecutive_losses": 0}
        save_state(state)
    return state


def circuit_breaker_tripped(state: dict) -> tuple[bool, str]:
    """
    Checks both safety limits against MT5's own account/history data —
    no separate bookkeeping to keep in sync, the terminal is the source
    of truth for what's actually happened on the account today.
    """
    day_start_balance = state.get("day_start_balance")
    if day_start_balance:
        today_start_utc = datetime.strptime(state["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        deals = mt5.history_deals_get(today_start_utc, datetime.now(timezone.utc))
        realized_today = sum(
            d.profit for d in (deals or [])
            if d.magic == MAGIC_NUMBER and d.entry == mt5.DEAL_ENTRY_OUT
        )
        loss_limit = -abs(day_start_balance * (DAILY_LOSS_LIMIT_PCT / 100))
        if realized_today <= loss_limit:
            return True, f"daily loss limit hit: {realized_today:.2f} <= {loss_limit:.2f}"

    if state.get("consecutive_losses", 0) >= MAX_CONSECUTIVE_LOSSES:
        return True, f"{state['consecutive_losses']} consecutive losses today"

    return False, ""


def update_consecutive_losses(state: dict) -> dict:
    """
    Recomputes the consecutive-loss streak from today's closed deals
    (our own magic number only), most recent first.
    """
    today_start_utc = datetime.strptime(state["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    deals = mt5.history_deals_get(today_start_utc, datetime.now(timezone.utc))
    closes = sorted(
        [d for d in (deals or []) if d.magic == MAGIC_NUMBER and d.entry == mt5.DEAL_ENTRY_OUT],
        key=lambda d: d.time,
        reverse=True,
    )
    streak = 0
    for d in closes:
        if d.profit < 0:
            streak += 1
        else:
            break
    state["consecutive_losses"] = streak
    save_state(state)
    return state


# --- Backend API -------------------------------------------------------------

def fetch_executable_signals() -> list:
    try:
        resp = requests.get(
            f"{BACKEND_URL}/api/analysis/signals/executable",
            headers={"X-Executor-Key": EXECUTOR_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.error(f"Failed to fetch executable signals: {e}")
        return []


def report_execution(signal_id: str, note: str, ticket=None, price=None, lot=None) -> None:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/analysis/signals/{signal_id}/mark-executed",
            headers={"X-Executor-Key": EXECUTOR_API_KEY},
            json={
                "mt5_ticket": str(ticket) if ticket is not None else None,
                "execution_price": price,
                "execution_lot_size": lot,
                "note": note,
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        # Logged but not re-raised: a failure to record this shouldn't
        # crash the loop, though it does mean the signal may be re-fetched
        # and re-evaluated next poll — fine for a skip, a problem for a
        # fill, so this is flagged loudly.
        log.error(f"Failed to report execution for signal {signal_id} ({note}): {e}")


# --- Symbol / pip helpers ----------------------------------------------------

def mt5_symbol(pair: str) -> str:
    """'EUR/USD' -> 'EURUSD' (+ MT5_SYMBOL_SUFFIX if your broker uses one)."""
    return pair.replace("/", "") + MT5_SYMBOL_SUFFIX


def pip_size(pair: str) -> float:
    if "JPY" in pair or "XAU" in pair:
        return 0.01
    return 0.0001


def pip_value_per_lot(pair: str) -> float:
    # Mirrors the exact constants used in the Journal's Risk Amount
    # auto-calc (frontend/app/(dashboard)/journal/page.tsx) so position
    # sizing here matches what the app already shows you per trade.
    if "XAU" in pair:
        return 1.0
    if "JPY" in pair:
        return 6.5
    return 10.0


def calc_lot_size(symbol: str, pair: str, balance: float, entry_price: float, stop_loss: float) -> float:
    pips = abs(entry_price - stop_loss) / pip_size(pair)
    if pips <= 0:
        return 0.0

    risk_amount = balance * (RISK_PCT_PER_TRADE / 100)
    raw_lot = risk_amount / (pips * pip_value_per_lot(pair))

    info = mt5.symbol_info(symbol)
    if info is None:
        log.warning(f"No symbol_info for {symbol}, using unrounded lot size {raw_lot}")
        return round(raw_lot, 2)

    step = info.volume_step or 0.01
    lot = round(raw_lot / step) * step
    lot = max(info.volume_min, min(info.volume_max, lot))
    return round(lot, 2)


# --- Freshness check (mirrors is_entry_still_fresh in auto_signal_engine.py) -

def is_entry_still_fresh(symbol: str, direction: str, entry_low, entry_high, atr: float) -> bool:
    """
    Re-checks the entry zone against a LIVE MT5 tick, right before the
    order is placed. The backend already does an equivalent check before
    saving the signal, but more time has passed since then (poll interval
    + network round-trip), so this is a second, closer-to-the-wire check
    — belt and suspenders for the exact problem that motivated this whole
    feature: by the time anything acts on a signal, price may have moved.
    """
    if entry_low is None or entry_high is None:
        return True

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        log.warning(f"No live tick for {symbol} — skipping freshness check, not blocking on it")
        return True

    # Use the side of the spread the trade would actually fill at.
    live_price = tick.ask if direction == "BUY" else tick.bid
    buffer = (atr or 0) * 0.25

    if direction == "BUY" and live_price > entry_high + buffer:
        log.info(f"{symbol} BUY — STALE: live {live_price} already above entry zone {entry_low}-{entry_high}")
        return False
    if direction == "SELL" and live_price < entry_low - buffer:
        log.info(f"{symbol} SELL — STALE: live {live_price} already below entry zone {entry_low}-{entry_high}")
        return False
    return True


# --- Order placement ---------------------------------------------------------

def place_order(symbol: str, direction: str, lot: float, stop_loss: float, take_profit: float) -> dict:
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"ok": False, "error": f"no tick for {symbol}"}

    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == "BUY" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": SLIPPAGE_POINTS,
        "magic": MAGIC_NUMBER,
        "comment": "ForexIntel-auto" + ("-demo" if IS_DEMO else ""),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    result = mt5.order_send(request)
    if result is None:
        return {"ok": False, "error": f"order_send returned None: {mt5.last_error()}"}
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"ok": False, "error": f"retcode {result.retcode}: {result.comment}"}

    return {"ok": True, "ticket": result.order, "price": result.price}


# --- Main loop ----------------------------------------------------------------

def init_mt5() -> None:
    ok = mt5.initialize(path=MT5_TERMINAL_PATH) if MT5_TERMINAL_PATH else mt5.initialize()
    if not ok:
        log.error(f"mt5.initialize() failed: {mt5.last_error()}")
        sys.exit(1)

    if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
        log.error(f"mt5.login() failed: {mt5.last_error()}")
        sys.exit(1)

    account = mt5.account_info()
    log.info(
        f"Connected to MT5 — account {account.login} on {account.server} "
        f"({'DEMO' if IS_DEMO else 'LIVE'}), balance {account.balance} {account.currency}"
    )
    if account.trade_allowed is False:
        log.warning("Algo Trading does NOT appear to be allowed on this account/terminal — "
                    "enable it in MT5 (Tools > Options > Expert Advisors) before relying on this.")


def process_signal(sig: dict, open_count: int) -> int:
    """Returns the updated open_count (incremented by 1 if a trade was placed)."""
    pair = sig["pair"]
    direction = sig["direction"]
    symbol = mt5_symbol(pair)

    if open_count >= MAX_CONCURRENT_TRADES:
        log.info(f"{pair} {sig['timeframe']} — max concurrent trades ({MAX_CONCURRENT_TRADES}) reached, skipping")
        report_execution(sig["id"], note=f"skipped: max concurrent trades ({MAX_CONCURRENT_TRADES}) reached")
        return open_count

    if not is_entry_still_fresh(symbol, direction, sig.get("entry_low"), sig.get("entry_high"), sig.get("atr", 0)):
        report_execution(sig["id"], note="skipped: stale entry zone at execution time (live price check)")
        return open_count

    account = mt5.account_info()
    if account is None:
        log.error("Could not read account info, skipping this signal")
        report_execution(sig["id"], note="skipped: could not read account balance")
        return open_count

    stop_loss = sig.get("stop_loss")
    take_profit = sig.get("take_profit_2") or sig.get("take_profit_1")
    if stop_loss is None or take_profit is None:
        log.warning(f"{pair} {sig['timeframe']} — missing SL/TP, skipping")
        report_execution(sig["id"], note="skipped: missing stop_loss or take_profit on signal")
        return open_count

    lot = calc_lot_size(symbol, pair, account.balance, sig["current_price"], stop_loss)
    if lot <= 0:
        log.warning(f"{pair} {sig['timeframe']} — computed lot size {lot}, skipping")
        report_execution(sig["id"], note=f"skipped: computed lot size was {lot}")
        return open_count

    log.info(f"Placing {direction} {symbol} lot={lot} SL={stop_loss} TP={take_profit} "
              f"(risk {RISK_PCT_PER_TRADE}% of {account.balance})")
    result = place_order(symbol, direction, lot, stop_loss, take_profit)

    if result["ok"]:
        log.info(f"✅ FILLED {symbol} {direction} ticket={result['ticket']} @ {result['price']}")
        report_execution(
            sig["id"],
            note=f"filled: ticket {result['ticket']} @ {result['price']}, lot {lot}",
            ticket=result["ticket"],
            price=result["price"],
            lot=lot,
        )
        return open_count + 1
    else:
        log.error(f"❌ FAILED {symbol} {direction}: {result['error']}")
        report_execution(sig["id"], note=f"failed: {result['error']}")
        return open_count


def main() -> None:
    if not BACKEND_URL or not EXECUTOR_API_KEY:
        log.error("BACKEND_URL and EXECUTOR_API_KEY must be set in .env")
        sys.exit(1)

    init_mt5()
    state = load_state()
    state = refresh_daily_state(state)

    log.info(f"Executor running — polling every {POLL_INTERVAL_SECONDS}s, "
              f"risk {RISK_PCT_PER_TRADE}%/trade, max {MAX_CONCURRENT_TRADES} concurrent, "
              f"daily loss limit {DAILY_LOSS_LIMIT_PCT}%, max {MAX_CONSECUTIVE_LOSSES} consecutive losses")

    while True:
        try:
            state = refresh_daily_state(state)
            state = update_consecutive_losses(state)

            tripped, reason = circuit_breaker_tripped(state)
            if tripped:
                log.warning(f"Circuit breaker tripped ({reason}) — skipping this poll, no new trades today")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            positions = mt5.positions_get()
            open_count = len(positions) if positions else 0

            signals = fetch_executable_signals()
            if signals:
                log.info(f"{len(signals)} executable signal(s) from backend")
            for sig in signals:
                open_count = process_signal(sig, open_count)

        except Exception as e:
            log.exception(f"Unhandled error in main loop: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
