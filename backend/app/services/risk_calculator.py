from app.config import settings


# Pip sizes per pair type
PIP_SIZE = {
    "JPY": 0.01,      # USD/JPY, EUR/JPY etc
    "XAU": 0.01,      # Gold (XAU/USD)
    "DEFAULT": 0.0001 # EUR/USD, GBP/USD, etc
}

# Pip value per standard lot (1.0 lot) in USD
PIP_VALUE_STANDARD = {
    "JPY": 1000,      # $1000 per pip per lot (approx for JPY pairs)
    "XAU": 100,       # $100 per pip per lot for Gold
    "DEFAULT": 10,    # $10 per pip per lot for standard pairs
}


def get_pair_type(pair: str) -> str:
    """Determine pip size category from pair name."""
    pair = pair.upper().replace("/", "").replace("-", "")
    if "JPY" in pair:
        return "JPY"
    elif "XAU" in pair:
        return "XAU"
    return "DEFAULT"


def calculate_pip_size(pair: str) -> float:
    """Return pip size for a given pair."""
    return PIP_SIZE[get_pair_type(pair)]


def calculate_sl_pips(pair: str, entry_price: float, stop_loss: float) -> float:
    """Calculate stop loss distance in pips."""
    pip_size = calculate_pip_size(pair)
    return round(abs(entry_price - stop_loss) / pip_size, 1)


def calculate_lot_size(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    pair: str,
) -> dict:
    """
    Calculate position size and all related risk metrics.

    Returns a dict with:
    - risk_amount: USD amount at risk
    - sl_pips: stop loss in pips
    - lot_size: position size in lots
    - pip_value: dollar value per pip for this lot size
    - max_loss: maximum possible loss in USD
    """
    pair_type = get_pair_type(pair)
    pip_size = PIP_SIZE[pair_type]
    pip_value_per_lot = PIP_VALUE_STANDARD[pair_type]

    # Step 1: How much USD are we risking?
    risk_amount = round(account_balance * (risk_pct / 100), 2)

    # Step 2: How many pips to stop loss?
    sl_pips = calculate_sl_pips(pair, entry_price, stop_loss)

    # Step 3: Lot size = risk / (sl_pips * pip_value_per_lot)
    if sl_pips == 0:
        lot_size = 0.0
    else:
        lot_size = round(risk_amount / (sl_pips * pip_value_per_lot), 2)

    # Step 4: Actual pip value for our lot size
    pip_value = round(lot_size * pip_value_per_lot, 2)

    return {
        "risk_amount": risk_amount,
        "sl_pips": sl_pips,
        "lot_size": lot_size,
        "pip_value": pip_value,
        "max_loss": risk_amount,
    }


def calculate_rr_ratio(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
) -> float:
    """Calculate risk to reward ratio."""
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    if risk == 0:
        return 0.0
    return round(reward / risk, 2)


def calculate_potential_profit(
    lot_size: float,
    entry_price: float,
    take_profit: float,
    pair: str,
) -> float:
    """Calculate potential profit in USD."""
    pair_type = get_pair_type(pair)
    pip_size = PIP_SIZE[pair_type]
    pip_value_per_lot = PIP_VALUE_STANDARD[pair_type]
    tp_pips = abs(take_profit - entry_price) / pip_size
    return round(lot_size * tp_pips * pip_value_per_lot, 2)


def calculate_full_risk(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    pair: str,
) -> dict:
    """
    Master function — returns everything the Risk Calculator page needs.
    """
    position = calculate_lot_size(
        account_balance, risk_pct, entry_price, stop_loss, pair
    )

    rr_ratio = calculate_rr_ratio(entry_price, stop_loss, take_profit)

    potential_profit = calculate_potential_profit(
        position["lot_size"], entry_price, take_profit, pair
    )

    # Safety checks
    warnings = []
    if rr_ratio < settings.MIN_RR_RATIO:
        warnings.append(
            f"⚠️ R:R ratio {rr_ratio} is below minimum {settings.MIN_RR_RATIO}. "
            f"Consider a better entry or target."
        )
    if risk_pct > 2.0:
        warnings.append(
            f"⚠️ Risk of {risk_pct}% is high. Professional traders risk 1-2% max."
        )
    if position["lot_size"] == 0:
        warnings.append("⚠️ Stop loss is too close to entry. Lot size is zero.")

    return {
        "pair": pair,
        "account_balance": account_balance,
        "risk_pct": risk_pct,
        "risk_amount": position["risk_amount"],
        "sl_pips": position["sl_pips"],
        "lot_size": position["lot_size"],
        "pip_value": position["pip_value"],
        "max_loss": position["max_loss"],
        "potential_profit": potential_profit,
        "rr_ratio": rr_ratio,
        "warnings": warnings,
    }