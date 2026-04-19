import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENEI_API_KEY = os.environ.get("OPENEI_API_KEY")
OPENEI_URL = "https://api.openei.org/utility_rates"


def get_rates_by_zip(zip_code: str) -> list[dict]:
    """
    Fetches real time-of-use electricity rates for a zip code from OpenEI URDB.
    Returns energy_rates list matching the format the AI engine expects.
    Falls back to default rates if API call fails.
    """
    try:
        params = {
            "version": 8,
            "api_key": OPENEI_API_KEY,
            "format": "json",
            "address": zip_code,
            "limit": 1,
            "detail": "full",
        }
        response = requests.get(OPENEI_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            print(f"No rates found for zip {zip_code}, using defaults.")
            return _default_rates()

        rate = items[0]
        return _parse_tou_rates(rate)

    except Exception as e:
        print(f"OpenEI API error: {e} — using default rates.")
        return _default_rates()


def _parse_tou_rates(rate: dict) -> list[dict]:
    """
    Parses OpenEI rate structure into hourly cost list.
    If the rate has real TOU schedules, uses them. Otherwise derives from flat rate.
    """
    energy_rate_structure = rate.get("energyratestructure", [])
    weekday_schedule = rate.get("energyweekdayschedule", [])

    # Try to extract TOU periods if available
    if energy_rate_structure and weekday_schedule:
        # Build hour -> rate mapping from the weekday schedule
        # weekday_schedule is a 12x24 matrix (months x hours) of period indices
        hour_rates = {}
        # Use first month (index 0) as representative
        hour_periods = weekday_schedule[0] if weekday_schedule else []
        for hour, period_idx in enumerate(hour_periods):
            try:
                tier = energy_rate_structure[period_idx][0]
                rate_val = tier.get("rate", 0) + tier.get("adj", 0)
                hour_rates[hour] = round(rate_val, 4)
            except (IndexError, KeyError, TypeError):
                hour_rates[hour] = 0.13

        return [{"hour": h, "cost_per_kwh": hour_rates.get(h, 0.13)} for h in range(24)]

    # Flat rate fallback — still useful for cost estimates
    flat_rate = 0.13
    try:
        flat_rate = rate["energyratestructure"][0][0]["rate"]
    except (KeyError, IndexError, TypeError):
        pass

    return _flat_to_tou(flat_rate)


def _flat_to_tou(base_rate: float) -> list[dict]:
    """
    Converts a flat rate into a realistic TOU curve so the optimizer still works.
    Peak hours cost more, off-peak cost less.
    """
    multipliers = {
        range(0, 6): 0.80,    # overnight cheap
        range(6, 9): 1.10,    # morning ramp
        range(9, 16): 1.20,   # midday
        range(16, 21): 1.50,  # evening peak
        range(21, 24): 0.90,  # late night
    }
    rates = []
    for hour in range(24):
        mult = 1.0
        for r, m in multipliers.items():
            if hour in r:
                mult = m
                break
        rates.append({"hour": hour, "cost_per_kwh": round(base_rate * mult, 4)})
    return rates


def _default_rates() -> list[dict]:
    return [
        {"hour": 0, "cost_per_kwh": 0.10},
        {"hour": 6, "cost_per_kwh": 0.12},
        {"hour": 12, "cost_per_kwh": 0.18},
        {"hour": 18, "cost_per_kwh": 0.25},
        {"hour": 22, "cost_per_kwh": 0.14},
    ]
