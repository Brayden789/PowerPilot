def compute_energy_results(data: dict) -> dict:
    """
    Pure Python computation of energy usage and costs from user input + rates.
    This runs before the AI call so Claude gets pre-computed context.
    """
    devices = data.get("devices", [])
    rates = data.get("energy_rates", [])

    rate_lookup = {r["hour"]: r["cost_per_kwh"] for r in rates}
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
    phantom_pct = round(phantom_kwh / total_kwh * 100) if total_kwh else 0

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
    }
