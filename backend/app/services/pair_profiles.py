"""
Per-pair profiles — each pair gets the rules that suit how it moves.

A profile, per pair and timeframe, says:
  * playbooks — "trend" (rules_engine: follow the move) and/or "range"
                (range_engine: fade the edges of a sideways market)
  * sl_atr    — stop size in ATR for the trend playbook (target is 2x)
  * sessions  — which trading sessions a signal may come from
                (None = any time the market is open)

DESIGNED_PROFILES below are starting assumptions based on how each pair
is known to behave. They are NOT trusted as-is: backtest_profiles.py
tries them and a few alternatives on OLDER data, then checks the winner
on RECENT data it never saw. Only combinations that pass are written to
app/pair_profiles.json, and only those trade live.

Live use is OFF until you set the Railway variable USE_PAIR_PROFILES=true.
While it is off, the scanner works exactly as before.
"""
import json
import os
from datetime import datetime
from typing import Optional

from app.services import range_engine, rules_engine

USE_PAIR_PROFILES = os.getenv("USE_PAIR_PROFILES", "false").strip().lower() == "true"

PROFILES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "pair_profiles.json")

# Sessions as UTC hours [start, end). The candle's CLOSE time is checked.
SESSIONS = {
    "asia": (23, 8),      # Tokyo / Sydney (wraps past midnight)
    "london": (7, 16),
    "newyork": (12, 21),
}

# The current live rules, expressed as a profile (used as the comparison
# baseline in the backtest).
BASELINE = {"playbooks": ["trend"], "sl_atr": 1.5, "sessions": None}

# Starting assumptions per pair. The backtest decides what survives.
DESIGNED_PROFILES = {
    "USD/CAD": {"H1": {"playbooks": ["trend"], "sl_atr": 1.5, "sessions": None},
                "H4": {"playbooks": ["trend"], "sl_atr": 1.5, "sessions": None}},
    "GBP/USD": {"H1": {"playbooks": ["range"], "sl_atr": 1.5, "sessions": ["london", "newyork"]},
                "H4": {"playbooks": ["trend"], "sl_atr": 1.5, "sessions": None}},
    "EUR/USD": {"H1": {"playbooks": ["range"], "sl_atr": 1.5, "sessions": ["london", "newyork"]},
                "H4": {"playbooks": ["trend", "range"], "sl_atr": 1.5, "sessions": None}},
    "AUD/USD": {"H1": {"playbooks": ["range"], "sl_atr": 1.5, "sessions": ["asia", "london"]},
                "H4": {"playbooks": ["range"], "sl_atr": 1.5, "sessions": None}},
    "USD/JPY": {"H1": {"playbooks": ["trend"], "sl_atr": 2.0, "sessions": ["asia", "newyork"]},
                "H4": {"playbooks": ["trend"], "sl_atr": 2.0, "sessions": None}},
    "XAU/USD": {"H1": {"playbooks": ["trend"], "sl_atr": 2.0, "sessions": ["london", "newyork"]},
                "H4": {"playbooks": ["trend"], "sl_atr": 2.0, "sessions": None}},
}


def in_sessions(close_time: Optional[datetime], sessions: Optional[list]) -> bool:
    if not sessions or close_time is None:
        return True
    hour = close_time.hour
    for name in sessions:
        start, end = SESSIONS[name]
        if (start <= hour < end) if start < end else (hour >= start or hour < end):
            return True
    return False


def evaluate_with_profile(pair: str, timeframe: str, ind: dict, htf_cross: Optional[str],
                          profile: dict, close_time: Optional[datetime] = None) -> dict:
    """
    Run the playbooks a profile allows. Same return shape as
    rules_engine.evaluate, plus "playbook".
      * sideways market + "range" allowed -> range playbook
      * otherwise + "trend" allowed       -> trend playbook (with the profile's stop size)
    """
    regime, _ = rules_engine.classify_regime(ind)
    if not in_sessions(close_time, profile.get("sessions")):
        return {"action": "STAND_ASIDE", "regime": regime,
                "reason": f"outside trading sessions {profile.get('sessions')}"}

    playbooks = profile.get("playbooks") or []
    if regime == "RANGING" and "range" in playbooks:
        return range_engine.evaluate_range(pair, timeframe, ind, regime)
    if "trend" in playbooks:
        return rules_engine.evaluate(pair, timeframe, ind, htf_cross,
                                     sl_atr=profile.get("sl_atr", rules_engine.SL_ATR))
    return {"action": "STAND_ASIDE", "regime": regime,
            "reason": f"{regime.lower()} market, profile only allows {'/'.join(playbooks) or 'nothing'}"}


def load_approved() -> dict:
    """{pair: {timeframe: profile}} for combinations that passed the backtest."""
    try:
        with open(PROFILES_FILE) as f:
            data = json.load(f)
        return data.get("profiles", {})
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[Profiles] could not read {PROFILES_FILE}: {e}")
        return {}


APPROVED = load_approved() if USE_PAIR_PROFILES else {}


def approved_profile(pair: str, timeframe: str) -> Optional[dict]:
    return APPROVED.get(pair, {}).get(timeframe)


def approved_pairs() -> list:
    return sorted(APPROVED.keys())
