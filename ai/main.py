"""
Main entrypoint for PowerPilot — run with: python main.py
Pulls real device + rate data from Snowflake instead of hardcoded sample input.
"""
import json
from db import get_devices_for_user, get_tou_rates, save_energy_profile
from optimizer import compute_energy_results
from ai_engine import generate_energy_recommendation, ask_energy_question

USER_ID = "u1"

if __name__ == "__main__":
    print(f"Fetching data for user {USER_ID} from Snowflake...")
    devices = get_devices_for_user(USER_ID)
    rates = get_tou_rates()

    print(f"Devices: {len(devices)} | Rate hours: {len(rates)}")

    data = {
        "user_id": USER_ID,
        "devices": devices,
        "energy_rates": rates,
    }

    print("\nComputing energy results...")
    computed = compute_energy_results(data)
    data["computed_results"] = computed
    print(json.dumps(computed, indent=2))

    print("\nSaving profile to Snowflake...")
    save_energy_profile(USER_ID, computed)
    print("Saved.")

    print("\nCalling AI engine for recommendations...")
    result = generate_energy_recommendation(data)
    print(json.dumps(result, indent=2))

    print("\nTesting chat feature...")
    answer = ask_energy_question("Which device should I turn off first to save the most money?", data)
    print(answer)
