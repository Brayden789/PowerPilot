"""
Quick test entrypoint — run with: python main.py
"""
import json
from optimizer import compute_energy_results
from ai_engine import generate_energy_recommendation, ask_energy_question
from rates_fetcher import get_rates_by_zip

SAMPLE_INPUT = {
    "user_id": "u1",
    "devices": [
        {"device_name": "TV", "power_on_watts": 100, "hours_on_per_day": 3, "hours_idle_per_day": 21},
        {"device_name": "Xbox", "power_on_watts": 120, "hours_on_per_day": 2, "hours_idle_per_day": 22},
        {"device_name": "Laptop", "power_on_watts": 60, "hours_on_per_day": 6, "hours_idle_per_day": 18},
    ],
    "energy_rates": [
        {"hour": 0, "cost_per_kwh": 0.10},
        {"hour": 6, "cost_per_kwh": 0.12},
        {"hour": 12, "cost_per_kwh": 0.18},
        {"hour": 18, "cost_per_kwh": 0.25},
        {"hour": 22, "cost_per_kwh": 0.14},
    ],
}

if __name__ == "__main__":
    print("Fetching real energy rates for zip code 90210...")
    SAMPLE_INPUT["energy_rates"] = get_rates_by_zip("90210")
    print(json.dumps(SAMPLE_INPUT["energy_rates"], indent=2))

    print("Computing energy results...")
    computed = compute_energy_results(SAMPLE_INPUT)
    SAMPLE_INPUT["computed_results"] = computed
    print(json.dumps(computed, indent=2))

    print("\nCalling AI engine for recommendations...")
    result = generate_energy_recommendation(SAMPLE_INPUT)
    print(json.dumps(result, indent=2))

    print("\nTesting chat feature...")
    answer = ask_energy_question("Which device should I turn off first to save the most money?", SAMPLE_INPUT)
    print(answer)
