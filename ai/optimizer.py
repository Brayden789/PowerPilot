"""
optimizer.py — PowerPilot energy computation engine.

Key improvement: HVAC devices (AC, heating) are only counted in the months
they actually run. No one uses AC in December or heat in July.
"""

# ---------------------------------------------------------------------------
# SEASONAL HVAC CONFIG
# ---------------------------------------------------------------------------
COOLING_MONTHS = {6, 7, 8, 9}
HEATING_MONTHS = {11, 12, 1, 2, 3}

COOLING_KEYWORDS = [
    "ac", "a/c", "air conditioner", "air conditioning",
    "central air", "window ac", "mini split", "mini-split",
    "swamp cooler", "evaporative cooler",
]
HEATING_KEYWORDS = [
    "heat", "heater", "heating", "furnace", "boiler",
    "heat pump", "space heater", "baseboard heat",
    "electric heat", "radiant heat", "floor heat",
]

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def _classify_device(device_name: str) -> str:
    """Return 'cooling', 'heating', or 'standard'."""
    name = device_name.lower()
    if any(k in name for k in COOLING_KEYWORDS):
        return "cooling"
    if any(k in name for k in HEATING_KEYWORDS):
        return "heating"
    return "standard"


def _device_active_in_month(device_name: str, month: int) -> bool:
    kind = _classify_device(device_name)
    if kind == "cooling":
        return month in COOLING_MONTHS
    if kind == "heating":
        return month in HEATING_MONTHS
    return True


def compute_energy_results(data: dict) -> dict:
    devices = data.get("devices", [])
    rates = data.get("energy_rates", [])

    if not devices:
        return _empty_results(rates)

    avg_rate = sum(r["cost_per_kwh"] for r in rates) / len(rates) if rates else 0.12

    breakdown = []
    total_kwh = 0.0

    for device in devices:
        on_watts = device.get("power_on_watts", 0)
        idle_watts = device.get("power_idle_watts", on_watts * 0.05)
        hours_on = device.get("hours_on_per_day", 0)
        hours_idle = device.get("hours_idle_per_day", 0)

        kwh_per_day = (on_watts * hours_on + idle_watts * hours_idle) / 1000
        cost_per_month = kwh_per_day * 30 * avg_rate
        total_kwh += kwh_per_day

        breakdown.append({
            "device_name": device["device_name"],
            "device_type": _classify_device(device["device_name"]),
            "kwh_per_day": round(kwh_per_day, 3),
            "cost_per_month": round(cost_per_month, 2),
        })

    total_cost_per_month = round(total_kwh * 30 * avg_rate, 2)

    sorted_rates = sorted(rates, key=lambda r: r["cost_per_kwh"])
    best_hours = [r["hour"] for r in sorted_rates[:6]]
    worst_hours = [r["hour"] for r in sorted_rates[-3:]]

    cheapest = sorted_rates[0]["cost_per_kwh"] if sorted_rates else avg_rate
    most_expensive = sorted_rates[-1]["cost_per_kwh"] if sorted_rates else avg_rate
    savings_pct = round((1 - cheapest / most_expensive) * 100) if most_expensive else 0
    potential_savings = round(total_cost_per_month * savings_pct / 100, 2)

    phantom_watts = sum(
        device.get("power_on_watts", 0) * 0.05 * device.get("hours_idle_per_day", 0)
        for device in devices
    )
    phantom_kwh = round(phantom_watts / 1000, 3)
    phantom_pct = round(phantom_kwh / total_kwh * 100) if total_kwh > 0 else 0

    power_score = _compute_power_score(devices, rates, worst_hours, phantom_pct, savings_pct)
    monthly_projection = _compute_monthly_projection(devices, avg_rate)

    return {
        "summary": {
            "total_kwh_per_day": round(total_kwh, 3),
            "total_cost_per_month": total_cost_per_month,
        },
        "breakdown": breakdown,
        "optimization": {
            "best_hours": best_hours,
            "worst_hours": worst_hours,
            "potential_savings_percent": savings_pct,
            "potential_monthly_savings_dollars": potential_savings,
        },
        "phantom_load": {
            "total_watts": round(phantom_watts, 1),
            "daily_kwh": phantom_kwh,
            "percentage_of_total": phantom_pct,
        },
        "power_score": power_score,
        "monthly_projection": monthly_projection,
    }


def _compute_monthly_projection(devices: list, avg_rate: float) -> dict:
    """
    Seasonal monthly cost projection.
    - AC only runs June–September, harder in July/August
    - Heat only runs November–March, hardest in Dec/Jan
    - Standard devices get a mild seasonal scalar
    """
    COOLING_INTENSITY = {6: 0.70, 7: 1.00, 8: 0.95, 9: 0.60}
    HEATING_INTENSITY = {11: 0.60, 12: 1.00, 1: 1.00, 2: 0.85, 3: 0.55}
    STANDARD_SCALAR = {
        1: 1.05, 2: 1.03, 3: 1.00, 4: 0.97,
        5: 0.95, 6: 0.96, 7: 0.98, 8: 0.97,
        9: 0.96, 10: 0.97, 11: 1.02, 12: 1.08,
    }

    projection = {}
    for month_idx, month_name in enumerate(MONTH_NAMES, start=1):
        month_cost = 0.0
        for device in devices:
            name = device["device_name"]
            kind = _classify_device(name)
            on_watts = device.get("power_on_watts", 0)
            idle_watts = device.get("power_idle_watts", on_watts * 0.05)
            hours_on = device.get("hours_on_per_day", 0)
            hours_idle = device.get("hours_idle_per_day", 0)

            if kind == "cooling":
                if month_idx not in COOLING_MONTHS:
                    continue
                intensity = COOLING_INTENSITY.get(month_idx, 0.8)
                kwh = (on_watts * intensity * hours_on + idle_watts * hours_idle) / 1000
            elif kind == "heating":
                if month_idx not in HEATING_MONTHS:
                    continue
                intensity = HEATING_INTENSITY.get(month_idx, 0.8)
                kwh = (on_watts * intensity * hours_on + idle_watts * hours_idle) / 1000
            else:
                scalar = STANDARD_SCALAR.get(month_idx, 1.0)
                kwh = ((on_watts * hours_on + idle_watts * hours_idle) / 1000) * scalar

            month_cost += kwh * 30 * avg_rate

        projection[month_name] = round(month_cost, 2)

    return projection


def _compute_power_score(devices, rates, worst_hours, phantom_pct, savings_pct):
    worst_set = set(worst_hours)
    total_on_hours = sum(d.get("hours_on_per_day", 0) for d in devices)
    peak_ratio = len(worst_set) / 24
    peak_usage_penalty = round(min(30, peak_ratio * total_on_hours * 5))
    inefficiency_penalty = round(min(30, phantom_pct * 0.6))
    off_peak_bonus = round(min(20, savings_pct * 0.2))
    score = 100 - peak_usage_penalty - inefficiency_penalty + off_peak_bonus
    return max(0, min(100, score))


def _empty_results(rates: list = None) -> dict:
    """
    Returns zeroed results. If rates are provided, best/worst hours are
    still computed so the UI can show the rate chart even with no devices.
    """
    sorted_rates = sorted(rates, key=lambda r: r["cost_per_kwh"]) if rates else []
    best_hours = [r["hour"] for r in sorted_rates[:6]]
    worst_hours = [r["hour"] for r in sorted_rates[-3:]]
    cheapest = sorted_rates[0]["cost_per_kwh"] if sorted_rates else 0.12
    priciest = sorted_rates[-1]["cost_per_kwh"] if sorted_rates else 0.12
    savings_pct = round((1 - cheapest / priciest) * 100) if priciest else 0

    return {
        "summary": {"total_kwh_per_day": 0.0, "total_cost_per_month": 0.0},
        "breakdown": [],
        "optimization": {
            "best_hours": best_hours,
            "worst_hours": worst_hours,
            "potential_savings_percent": savings_pct,
            "potential_monthly_savings_dollars": 0.0,
        },
        "phantom_load": {"total_watts": 0.0, "daily_kwh": 0.0, "percentage_of_total": 0},
        "power_score": 50,
        "monthly_projection": {m: 0.0 for m in MONTH_NAMES},
    }
