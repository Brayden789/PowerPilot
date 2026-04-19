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


def get_rates_for_zip(zip_code: str) -> list[dict]:
    """
    Pulls energy rates for a zip code from Snowflake.
    Falls back to rates_fetcher.py if none found in DB.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT hour, cost_per_kwh
        FROM energy_rates
        WHERE zip_code = %s
        ORDER BY hour
    """, (zip_code,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        # fall back to live fetch if no rates in DB for this zip
        from rates_fetcher import get_rates_by_zip
        return get_rates_by_zip(zip_code)

    return [{"hour": row[0], "cost_per_kwh": row[1]} for row in rows]


def get_zip_for_user(user_id: str) -> str:
    """
    Looks up a user's zip code from the users table.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT zip_code FROM users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    return row[0] if row else "13037"  # default zip if not found


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
