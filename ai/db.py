import snowflake.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return snowflake.connector.connect(
        account=os.environ.get("SNOWFLAKE_ACCOUNT"),    # e.g. abc12345.us-east-1
        user=os.environ.get("SNOWFLAKE_USER"),          # your snowflake username
        password=os.environ.get("SNOWFLAKE_PASSWORD"),  # your snowflake password
        database="POWERPILOT",
        schema="MAIN",
    )


def get_devices_for_user(user_id: str) -> list[dict]:
    """
    Pulls all devices for a user from Snowflake.
    Returns a list of dicts matching the format optimizer.py expects.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT device_name, power_on_watts, power_idle_watts, hours_on_per_day, hours_idle_per_day
        FROM devices
        WHERE user_id = %s
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    devices = []
    for row in rows:
        device_name, power_on_watts, power_idle_watts, hours_on_per_day, hours_idle_per_day = row
        device = {
            "device_name": device_name,
            "power_on_watts": power_on_watts or 0,
            "hours_on_per_day": hours_on_per_day or 0,
            "hours_idle_per_day": hours_idle_per_day or 0,
        }
        # only include idle watts if it was set, optimizer will default to 5% otherwise
        if power_idle_watts is not None:
            device["power_idle_watts"] = power_idle_watts
        devices.append(device)

    return devices


def get_tou_rates() -> list[dict]:
    """
    Returns a realistic hardcoded time-of-use rate curve.
    Cheap overnight, moderate midday, expensive evening peak.
    """
    base = 0.12
    multipliers = [
        (range(0, 6),   0.80),
        (range(6, 9),   1.10),
        (range(9, 16),  1.20),
        (range(16, 21), 1.50),
        (range(21, 24), 0.90),
    ]
    rates = []
    for h in range(24):
        mult = next((m for r, m in multipliers if h in r), 1.0)
        rates.append({"hour": h, "cost_per_kwh": round(base * mult, 4)})
    return rates


def save_energy_profile(user_id: str, computed_results: dict):
    """
    Saves the full computed_results JSON blob to user_energy_profiles.
    """
    import json
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO user_energy_profiles (user_id, data)
        SELECT %s, PARSE_JSON(%s)
    """, (user_id, json.dumps(computed_results)))

    conn.commit()
    cursor.close()
    conn.close()
