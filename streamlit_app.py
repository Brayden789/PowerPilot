import streamlit as st
import snowflake.connector
import json
import os
import requests
import pandas as pd

# -----------------------------------------
# PAGE CONFIG
# -----------------------------------------
st.set_page_config(
    page_title="PowerPilot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------
# DEVICE DEFAULTS
# -----------------------------------------
DEVICE_DEFAULTS = {
    # Kitchen
    "refrigerator":         (150,  24,  0),
    "fridge":               (150,  24,  0),
    "microwave":            (1200, 0.5, 0),
    "dishwasher":           (1800, 1.5, 0),
    "oven":                 (2400, 1.0, 0),
    "stove":                (1500, 1.0, 0),
    "coffee maker":         (800,  0.5, 0),
    "toaster":              (900,  0.2, 0),
    "toaster oven":         (1200, 0.5, 0),
    "kettle":               (1500, 0.3, 0),
    # Laundry
    "washer":               (500,  1.0, 0),
    "washing machine":      (500,  1.0, 0),
    "dryer":                (5000, 1.0, 0),
    "clothes dryer":        (5000, 1.0, 0),
    # Lighting
    "led light":            (10,   6,  18),
    "led lights":           (10,   6,  18),
    "led bulb":             (10,   6,  18),
    "light":                (60,   6,  18),
    "lights":               (60,   6,  18),
    "lamp":                 (60,   5,  19),
    "ceiling light":        (60,   6,  18),
    "ceiling fan":          (75,   6,  18),
    # Entertainment
    "tv":                   (100,  4,  20),
    "television":           (100,  4,  20),
    "monitor":              (30,   8,  16),
    "gaming pc":            (400,  4,  20),
    "desktop pc":           (300,  6,  18),
    "desktop":              (300,  6,  18),
    "laptop":               (60,   6,  18),
    "xbox":                 (120,  3,  21),
    "playstation":          (120,  3,  21),
    "ps5":                  (200,  3,  21),
    "ps4":                  (140,  3,  21),
    "nintendo switch":      (18,   3,  21),
    "router":               (10,   24,  0),
    "modem":                (10,   24,  0),
    # Climate
    "air conditioner":      (1500, 8,  16),
    "ac":                   (1500, 8,  16),
    "window ac":            (1200, 8,  16),
    "central ac":           (3500, 8,  16),
    "heater":               (1500, 8,  16),
    "space heater":         (1500, 8,  16),
    "electric heater":      (1500, 8,  16),
    "furnace":              (600,  8,  16),
    "heat pump":            (1000, 8,  16),
    "electric furnace":     (10000, 8, 16),
    # Water
    "water heater":         (4000, 3,  21),
    "electric water heater": (4000, 3, 21),
    # Other
    "vacuum":               (1400, 0.5, 0),
    "hair dryer":           (1875, 0.3, 0),
    "phone charger":        (5,    8,  16),
    "tablet charger":       (10,   6,  18),
    "electric blanket":     (200,  6,  18),
    "dehumidifier":         (280,  6,  18),
    "humidifier":           (50,   8,  16),
    "pool pump":            (1500, 8,  16),
    "hot tub":              (3000, 2,  22),
    "garage door opener":   (350,  0.1, 0),
    "security camera":      (15,   24,  0),
    "smart speaker":        (3,    24,  0),
    "alexa":                (3,    24,  0),
    "google home":          (3,    24,  0),
    "printer":              (30,   0.5, 0),
}

SEASONAL_MONTHS = {
    "air conditioner":      [6, 7, 8, 9],
    "ac":                   [6, 7, 8, 9],
    "window ac":            [6, 7, 8, 9],
    "central ac":           [6, 7, 8, 9],
    "heater":               [11, 12, 1, 2, 3],
    "space heater":         [11, 12, 1, 2, 3],
    "electric heater":      [11, 12, 1, 2, 3],
    "furnace":              [11, 12, 1, 2, 3],
    "heat pump":            [11, 12, 1, 2, 3],
    "electric furnace":     [11, 12, 1, 2, 3],
    "pool pump":            [5, 6, 7, 8, 9],
}

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_device_defaults(name: str):
    key = name.strip().lower()
    if key in DEVICE_DEFAULTS:
        return DEVICE_DEFAULTS[key]
    for k, v in DEVICE_DEFAULTS.items():
        if k in key or key in k:
            return v
    return (100, 2, 22)


def is_seasonal(name: str):
    return name.strip().lower() in SEASONAL_MONTHS


def get_active_months(name: str):
    return SEASONAL_MONTHS.get(name.strip().lower(), list(range(1, 13)))


# -----------------------------------------
# STYLES
# -----------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
html, body, [class*="css"] { background-color: #080C12; color: #E8EDF5; font-family: 'Syne', sans-serif; }
.main { background-color: #080C12; }
.pilot-header { display: flex; align-items: center; gap: 14px; padding: 2rem 0 1rem 0; border-bottom: 1px solid #1E2A3A; margin-bottom: 0.5rem; }
.pilot-logo { font-size: 2.4rem; }
.pilot-title { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 2rem; color: #00D4FF; letter-spacing: -0.02em; margin: 0; }
.pilot-tagline { font-size: 0.82rem; color: #4A6080; margin: 0.2rem 0 0 0; font-family: 'Space Mono', monospace; font-style: italic; }
@keyframes scoreCount { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes barGrow { from { width: 0%; } to { width: var(--target-width); } }
.score-ring-wrap { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1.5rem; background: linear-gradient(135deg, #0D1520 0%, #111C2E 100%); border: 1px solid #1E2A3A; border-radius: 16px; }
.score-number { font-family: 'Space Mono', monospace; font-size: 4rem; font-weight: 700; color: #00D4FF; line-height: 1; animation: scoreCount 0.8s ease-out forwards; }
.score-label { font-size: 0.75rem; color: #4A6080; letter-spacing: 0.12em; text-transform: uppercase; margin-top: 0.4rem; font-family: 'Space Mono', monospace; }
.score-bar-bg { width: 100%; height: 6px; background: #1E2A3A; border-radius: 3px; margin-top: 1rem; overflow: hidden; }
.score-bar-fill { height: 6px; border-radius: 3px; background: linear-gradient(90deg, #0066FF, #00D4FF); animation: barGrow 1.2s ease-out forwards; }
.metric-card { background: linear-gradient(135deg, #0D1520 0%, #111C2E 100%); border: 1px solid #1E2A3A; border-radius: 16px; padding: 1.4rem 1.6rem; height: 100%; }
.metric-value { font-family: 'Space Mono', monospace; font-size: 2rem; font-weight: 700; color: #E8EDF5; line-height: 1.1; }
.metric-unit { font-size: 0.85rem; color: #4A6080; font-family: 'Space Mono', monospace; }
.metric-label { font-size: 0.75rem; color: #4A6080; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 0.3rem; }
.metric-sub { font-size: 0.7rem; color: #2A3A50; margin-top: 0.2rem; font-family: 'Space Mono', monospace; }
.metric-accent { color: #00D4FF; }
.metric-accent-green { color: #00FF94; }
.metric-accent-orange { color: #FF6B35; }
.section-header { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 1rem; color: #4A6080; text-transform: uppercase; letter-spacing: 0.12em; margin: 2rem 0 1rem 0; display: flex; align-items: center; gap: 8px; }
.section-line { flex: 1; height: 1px; background: #1E2A3A; }
.hour-bar-wrap { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 80px; cursor: pointer; }
.hour-bar-wrap:hover .hour-tooltip { display: block; }
.hour-tooltip { display: none; position: absolute; bottom: 110%; left: 50%; transform: translateX(-50%); background: #1E2A3A; color: #E8EDF5; font-family: 'Space Mono', monospace; font-size: 0.6rem; padding: 4px 7px; border-radius: 5px; white-space: nowrap; z-index: 10; border: 1px solid #2A3A50; }
.hour-bar { width: 100%; border-radius: 3px 3px 0 0; transition: opacity 0.15s; }
.hour-bar-wrap:hover .hour-bar { opacity: 0.75; }
.hour-label { font-size: 0.48rem; font-family: 'Space Mono', monospace; color: #4A6080; text-align: center; margin-top: 3px; }
.device-row { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; padding: 0.8rem 1rem; border-bottom: 1px solid #1E2A3A; align-items: center; }
.device-row:last-child { border-bottom: none; }
.device-row-header { font-size: 0.7rem; color: #4A6080; text-transform: uppercase; letter-spacing: 0.1em; font-family: 'Space Mono', monospace; }
.device-name { font-weight: 600; color: #E8EDF5; }
.device-val { font-family: 'Space Mono', monospace; font-size: 0.85rem; color: #A0B4CC; }
.device-cost { font-family: 'Space Mono', monospace; font-size: 0.85rem; color: #00FF94; }
.rec-card { background: #0D1520; border: 1px solid #1E2A3A; border-left: 3px solid #00D4FF; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 0.6rem; font-size: 0.9rem; color: #C0D0E0; line-height: 1.5; }
.insight-card { background: #0D1520; border: 1px solid #1E2A3A; border-left: 3px solid #00FF94; border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 0.6rem; font-size: 0.9rem; color: #C0D0E0; line-height: 1.5; }
.phantom-bar-bg { width: 100%; height: 8px; background: #1E2A3A; border-radius: 4px; margin-top: 0.5rem; }
.phantom-bar-fill { height: 8px; border-radius: 4px; background: linear-gradient(90deg, #FF6B35, #FF3366); }
.chat-bubble-user { background: #1E2A3A; border-radius: 12px 12px 2px 12px; padding: 0.8rem 1.1rem; margin: 0.5rem 0; font-size: 0.9rem; color: #E8EDF5; max-width: 80%; margin-left: auto; }
.chat-bubble-ai { background: #0D1A2E; border: 1px solid #1E2A3A; border-radius: 12px 12px 12px 2px; padding: 0.8rem 1.1rem; margin: 0.5rem 0; font-size: 0.9rem; color: #C0D0E0; max-width: 80%; line-height: 1.5; }
.stButton > button { background: linear-gradient(135deg, #0066FF, #00D4FF); color: #080C12; font-family: 'Syne', sans-serif; font-weight: 700; border: none; border-radius: 8px; padding: 0.5rem 1.5rem; font-size: 0.9rem; letter-spacing: 0.05em; }
.stButton > button:hover { opacity: 0.85; }
.stTextInput > div > div > input { background: #0D1520; border: 1px solid #1E2A3A; border-radius: 8px; color: #E8EDF5; font-family: 'Space Mono', monospace; font-size: 0.85rem; }
.stNumberInput > div > div > input { background: #0D1520; border: 1px solid #1E2A3A; border-radius: 8px; color: #E8EDF5; font-family: 'Space Mono', monospace; }
.stSelectbox > div > div { background: #0D1520; border: 1px solid #1E2A3A; border-radius: 8px; color: #E8EDF5; }
div[data-testid="stTab"] button { font-family: 'Syne', sans-serif; font-weight: 600; color: #4A6080; }
div[data-testid="stTab"] button[aria-selected="true"] { color: #00D4FF; border-bottom-color: #00D4FF; }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------
# SNOWFLAKE
# The key fix: reads use a cached connection, writes use a
# FRESH connection with autocommit=True every single time.
# This is the only reliable pattern on Streamlit Cloud.
# -----------------------------------------
def _sf_creds():
    return dict(
        account=st.secrets["SNOWFLAKE_ACCOUNT"],
        user=st.secrets["SNOWFLAKE_USER"],
        password=st.secrets["SNOWFLAKE_PASSWORD"],
        database="POWERPILOT",
        schema="MAIN",
    )


def run_query(query, params=None):
    """SELECT queries via fresh connection to avoid stale cached results after writes."""
    conn = snowflake.connector.connect(**_sf_creds())
    cursor = conn.cursor()
    try:
        cursor.execute(query, params) if params else cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)
    finally:
        cursor.close()
        conn.close()


def run_write(query, params=None):
    """
    INSERT / DELETE via a fresh autocommit connection.
    autocommit=True means Snowflake commits immediately on execute —
    no conn.commit() needed, and no stale cached connection issues.
    """
    creds = _sf_creds()
    creds["autocommit"] = True
    conn = snowflake.connector.connect(**creds)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params) if params else cursor.execute(query)
    finally:
        cursor.close()
        conn.close()


# -----------------------------------------
# DATA FUNCTIONS
# -----------------------------------------
def get_devices(user_id):
    df = run_query(
        "SELECT device_name, power_on_watts, power_idle_watts, hours_on_per_day, hours_idle_per_day "
        "FROM POWERPILOT.MAIN.devices WHERE user_id = %s",
        params=(user_id,)
    )
    devices = []
    for _, row in df.iterrows():
        def safe(val, default=0):
            try:
                f = float(val)
                return f if f == f else default
            except (TypeError, ValueError):
                return default

        device = {
            "device_name": str(row["DEVICE_NAME"]),
            "power_on_watts": safe(row["POWER_ON_WATTS"]),
            "hours_on_per_day": safe(row["HOURS_ON_PER_DAY"]),
            "hours_idle_per_day": safe(row["HOURS_IDLE_PER_DAY"]),
        }
        idle = safe(row["POWER_IDLE_WATTS"], default=None)
        if idle is not None:
            device["power_idle_watts"] = idle
        devices.append(device)
    return devices


def get_rates():
    """Realistic hardcoded TOU curve — cheap overnight, expensive evening peak."""
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


def add_device_to_db(user_id, device_name, power_on_watts, hours_on, hours_idle):
    run_write(
        "INSERT INTO POWERPILOT.MAIN.devices "
        "(user_id, device_name, power_on_watts, hours_on_per_day, hours_idle_per_day) "
        "VALUES (%s, %s, %s, %s, %s)",
        params=(user_id, device_name, float(power_on_watts), float(hours_on), float(hours_idle))
    )


def delete_device_from_db(user_id, device_name):
    run_write(
        "DELETE FROM POWERPILOT.MAIN.devices WHERE user_id = %s AND device_name = %s",
        params=(user_id, device_name)
    )


# -----------------------------------------
# OPTIMIZER
# -----------------------------------------
def compute_energy_results(devices, rates):
    sorted_rates_base = sorted(rates, key=lambda r: r["cost_per_kwh"]) if rates else []
    best_hours_base = [r["hour"] for r in sorted_rates_base[:6]]
    worst_hours_base = [r["hour"] for r in sorted_rates_base[-3:]]
    cheapest_base = sorted_rates_base[0]["cost_per_kwh"] if sorted_rates_base else 0.12
    priciest_base = sorted_rates_base[-1]["cost_per_kwh"] if sorted_rates_base else 0.12
    savings_pct_base = round((1 - cheapest_base / priciest_base) * 100) if priciest_base else 0

    if not devices:
        return {
            "summary": {"total_kwh_per_day": 0, "total_cost_per_month": 0},
            "breakdown": [],
            "optimization": {
                "best_hours": best_hours_base,
                "worst_hours": worst_hours_base,
                "potential_savings_percent": savings_pct_base,
                "potential_monthly_savings_dollars": 0,
            },
            "phantom_load": {"total_watts": 0, "daily_kwh": 0, "percentage_of_total": 0},
            "power_score": 0,
            "monthly_projection": {m: 0 for m in MONTH_NAMES},
        }

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
        d.get("power_on_watts", 0) * 0.05 * d.get("hours_idle_per_day", 0)
        for d in devices
    )
    phantom_kwh = round(phantom_watts / 1000, 3)
    phantom_pct = round(phantom_kwh / total_kwh * 100) if total_kwh else 0

    worst_set = set(worst_hours)
    total_on_hours = sum(d.get("hours_on_per_day", 0) for d in devices)
    peak_ratio = len(worst_set) / 24
    peak_usage_penalty = round(min(30, peak_ratio * total_on_hours * 5))
    inefficiency_penalty = round(min(30, phantom_pct * 0.6))
    off_peak_bonus = round(min(20, savings_pct * 0.2))
    power_score = max(0, min(100, 100 - peak_usage_penalty - inefficiency_penalty + off_peak_bonus))

    monthly_projection = {}
    for i, month in enumerate(MONTH_NAMES):
        month_num = i + 1
        month_kwh = 0.0
        for device in devices:
            name_key = device["device_name"].strip().lower()
            active_months = get_active_months(name_key)
            if month_num not in active_months:
                continue
            on_watts = device.get("power_on_watts", 0)
            idle_watts = device.get("power_idle_watts", on_watts * 0.05)
            hours_on = device.get("hours_on_per_day", 0)
            hours_idle = device.get("hours_idle_per_day", 0)
            kwh_per_day = (on_watts * hours_on + idle_watts * hours_idle) / 1000
            month_kwh += kwh_per_day
        monthly_projection[month] = round(month_kwh * 30 * avg_rate, 2)

    return {
        "summary": {
            "total_kwh_per_day": round(total_kwh, 3),
            "total_cost_per_month": total_cost_per_month
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
            "percentage_of_total": phantom_pct
        },
        "power_score": power_score,
        "monthly_projection": monthly_projection,
    }


# -----------------------------------------
# AI ENGINE
# -----------------------------------------
def call_groq(prompt, max_tokens=1024):
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def generate_recommendation(devices, rates, computed):
    power_score = computed.get("power_score", 50)
    prompt = f"""You are an energy optimization AI. Analyze this user's energy data and return recommendations.
Devices: {json.dumps(devices)}
Rates: {json.dumps(rates)}
Summary: {json.dumps(computed)}
PowerScore is {power_score}/100.
Return ONLY a JSON object, no extra text:
{{"current_energy_score":{power_score},"new_energy_score":<int higher than {power_score} max 100>,"recommendations":["<tip>","<tip>","<tip>"],"estimated_monthly_savings":<float>,"insights":["<insight>","<insight>"],"best_usage_hours":[<ints 0-23>],"worst_usage_hours":[<ints 0-23>]}}"""
    raw = call_groq(prompt, max_tokens=1024)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception:
        return {"error": "Failed to parse AI response"}


def lookup_device_specs(device_name: str) -> dict:
    """
    Uses Groq to look up US average wattage, hours on, and hours idle
    for a given device. Returns a dict with watts, hours_on, hours_idle.
    """
    prompt = f"""You are a home energy expert. A user wants to add "{device_name}" to their energy tracker.
Return the typical US household average energy usage for this device as JSON only, no extra text:
{{
  "watts": <integer, typical running wattage>,
  "hours_on": <float, typical hours used per day>,
  "hours_idle": <float, typical hours in standby/idle per day>,
  "note": "<one short sentence about this device's energy use>"
}}
Base your answer on US Energy Information Administration averages or well-known appliance data.
If the device is seasonal (AC, heater), use typical active-season daily hours."""
    try:
        raw = call_groq(prompt, max_tokens=200)
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        result = json.loads(raw)
        return {
            "watts": int(result.get("watts", 100)),
            "hours_on": float(result.get("hours_on", 2.0)),
            "hours_idle": float(result.get("hours_idle", 0.0)),
            "note": result.get("note", ""),
        }
    except Exception:
        return {"watts": 100, "hours_on": 2.0, "hours_idle": 0.0, "note": ""}


def ask_question(question, devices, rates, computed):
    prompt = f"""You are PowerPilot, a friendly home energy advisor.
Devices: {json.dumps(devices)}
Rates: {json.dumps(rates)}
Summary: {json.dumps(computed)}
User asks: "{question}"
Answer in 2-4 sentences. Be specific, friendly, practical. No jargon."""
    return call_groq(prompt, max_tokens=512)


# -----------------------------------------
# SESSION STATE
# -----------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None
if "refresh_devices" not in st.session_state:
    st.session_state.refresh_devices = 0
if "device_suggestion" not in st.session_state:
    st.session_state.device_suggestion = None
if "device_search_name" not in st.session_state:
    st.session_state.device_search_name = ""
if "device_watts" not in st.session_state:
    st.session_state.device_watts = 100
if "device_hours_on" not in st.session_state:
    st.session_state.device_hours_on = 2.0
if "device_hours_idle" not in st.session_state:
    st.session_state.device_hours_idle = 0.0

USER_ID = "u1"

# -----------------------------------------
# LOAD DATA
# -----------------------------------------
_placeholder = st.empty()
with _placeholder:
    with st.spinner("Loading your energy profile..."):
        _ = st.session_state.refresh_devices
        devices = get_devices(USER_ID)
        rates = get_rates()
_placeholder.empty()

computed = compute_energy_results(devices, rates)

# -----------------------------------------
# HEADER
# -----------------------------------------
st.markdown("""
<div class="pilot-header">
    <div class="pilot-logo">⚡</div>
    <div>
        <div class="pilot-title">PowerPilot</div>
        <div class="pilot-tagline">Most people think saving energy means using less. When you use it matters just as much.</div>
    </div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------
# TOP METRICS
# -----------------------------------------
power_score = computed["power_score"]
total_kwh = computed["summary"]["total_kwh_per_day"]
total_cost = computed["summary"]["total_cost_per_month"]
potential_savings = computed["optimization"]["potential_monthly_savings_dollars"]
phantom_pct = computed["phantom_load"]["percentage_of_total"]
annual_cost = round(total_cost * 12, 2)

col1, col2, col3, col4, col5 = st.columns([1.2, 1, 1, 1, 1])

with col1:
    st.markdown(f"""
<div class="score-ring-wrap">
    <div class="score-number">{power_score}</div>
    <div class="score-label">PowerScore</div>
    <div class="score-bar-bg">
        <div class="score-bar-fill" style="--target-width:{power_score}%;width:{power_score}%"></div>
    </div>
</div>
""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
<div class="metric-card">
    <div class="metric-value metric-accent">{total_kwh}<span class="metric-unit"> kWh</span></div>
    <div class="metric-label">Daily Usage</div>
</div>
""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""
<div class="metric-card">
    <div class="metric-value">${total_cost}<span class="metric-unit">/mo</span></div>
    <div class="metric-label">Est. Monthly Cost</div>
    <div class="metric-sub">${annual_cost}/yr</div>
</div>
""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""
<div class="metric-card">
    <div class="metric-value metric-accent-green">${potential_savings}<span class="metric-unit">/mo</span></div>
    <div class="metric-label">Potential Savings</div>
    <div class="metric-sub">${round(potential_savings * 12, 2)}/yr</div>
</div>
""", unsafe_allow_html=True)

with col5:
    st.markdown(f"""
<div class="metric-card">
    <div class="metric-value metric-accent-orange">{phantom_pct}<span class="metric-unit">%</span></div>
    <div class="metric-label">Phantom Load</div>
    <div class="metric-sub">idle device waste</div>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------
# TABS
# -----------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "⚡ Rates & Hours", "📊 Devices", "📈 Projection", "🤖 AI Advisor", "💬 Chat"
])

# ── TAB 1: RATES & HOURS ──
with tab1:
    st.markdown('<div class="section-header">Time-of-Use Rates <div class="section-line"></div></div>',
                unsafe_allow_html=True)

    best_hours = set(computed["optimization"]["best_hours"])
    worst_hours = set(computed["optimization"]["worst_hours"])
    rate_map = {r["hour"]: r["cost_per_kwh"] for r in rates}
    max_rate = max(rate_map.values()) if rate_map else 0.25
    min_rate = min(rate_map.values()) if rate_map else 0.10

    bars_html = '<div style="display:grid;grid-template-columns:repeat(24,1fr);gap:3px;align-items:end;height:100px;">'
    for h in range(24):
        rate = rate_map.get(h, 0.12)
        height_pct = int(((rate - min_rate) / (max_rate - min_rate + 0.001)) * 75 + 25)
        color = "#FF3366" if h in worst_hours else ("#00FF94" if h in best_hours else "#1E3A5F")
        bars_html += f"""<div class="hour-bar-wrap">
    <div class="hour-tooltip">{h:02d}:00 — ${rate:.4f}/kWh</div>
    <div class="hour-bar" style="background:{color};height:{height_pct}%;"></div>
</div>"""
    bars_html += "</div>"

    labels_html = '<div style="display:grid;grid-template-columns:repeat(24,1fr);gap:3px;margin-top:4px;">'
    for h in range(24):
        labels_html += f'<div class="hour-label">{h:02d}</div>'
    labels_html += "</div>"

    st.markdown(f"""
<div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;padding:1.5rem;">
    <div style="display:flex;justify-content:space-between;margin-bottom:0.8rem;">
        <span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;">HOUR OF DAY — hover for rate</span>
        <span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;">
            <span style="color:#00FF94;">■</span> Cheapest &nbsp;
            <span style="color:#FF3366;">■</span> Most Expensive &nbsp;
            <span style="color:#1E3A5F;">■</span> Mid
        </span>
    </div>
    {bars_html}{labels_html}
</div>
""", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
<div class="metric-card" style="margin-top:1rem;">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Best Hours to Run Devices</div>
    <div style="font-family:Space Mono,monospace;font-size:1.1rem;color:#00FF94;margin-top:0.5rem;">{", ".join(f"{h:02d}:00" for h in sorted(best_hours)) or "—"}</div>
</div>
""", unsafe_allow_html=True)

    with col_b:
        st.markdown(f"""
<div class="metric-card" style="margin-top:1rem;">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Avoid These Hours</div>
    <div style="font-family:Space Mono,monospace;font-size:1.1rem;color:#FF3366;margin-top:0.5rem;">{", ".join(f"{h:02d}:00" for h in sorted(worst_hours)) or "—"}</div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top:2rem;">Hidden Energy Waste <div class="section-line"></div></div>',
                unsafe_allow_html=True)

    phantom_watts = computed["phantom_load"]["total_watts"]
    phantom_kwh = computed["phantom_load"]["daily_kwh"]

    st.markdown(f"""
<div class="metric-card">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Phantom Load</div>
    <div style="font-family:Space Mono,monospace;font-size:1.5rem;color:#FF6B35;margin-top:0.3rem;">{phantom_pct}% of total usage</div>
    <div style="font-size:0.8rem;color:#4A6080;margin-top:0.3rem;">{phantom_watts}W idle draw · {phantom_kwh} kWh/day wasted</div>
    <div class="phantom-bar-bg"><div class="phantom-bar-fill" style="width:{min(phantom_pct,100)}%"></div></div>
</div>
""", unsafe_allow_html=True)

# ── TAB 2: DEVICES ──
with tab2:
    st.markdown('<div class="section-header">Device Breakdown <div class="section-line"></div></div>',
                unsafe_allow_html=True)

    breakdown = computed["breakdown"]
    if not breakdown:
        st.info("No devices added yet. Add your first device below.")
    else:
        st.markdown("""
<div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;overflow:hidden;">
    <div class="device-row device-row-header">
        <div>Device</div><div>kWh/day</div><div>Cost/month</div><div>Share</div>
    </div>
""", unsafe_allow_html=True)
        for item in breakdown:
            share = round(item["kwh_per_day"] / total_kwh * 100) if total_kwh else 0
            st.markdown(f"""
<div class="device-row">
    <div class="device-name">{item['device_name']}</div>
    <div class="device-val">{item['kwh_per_day']}</div>
    <div class="device-cost">${item['cost_per_month']}</div>
    <div class="device-val">{share}%</div>
</div>
""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top:2rem;">Add a Device <div class="section-line"></div></div>',
                unsafe_allow_html=True)

    # Step 1: name + Search
    srch_col1, srch_col2 = st.columns([3, 1])
    with srch_col1:
        search_name = st.text_input("Device Name", placeholder="e.g. Refrigerator, AC, TV...", key="device_search_input")
    with srch_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        do_search = st.button("🔍 Search", use_container_width=True)

    if do_search:
        if not search_name.strip():
            st.warning("Enter a device name first.")
        else:
            with st.spinner(f"Looking up US average specs for {search_name}..."):
                suggestion = lookup_device_specs(search_name)
            st.session_state.device_suggestion = suggestion
            st.session_state.device_search_name = search_name.strip()
            st.session_state.device_watts = suggestion["watts"]
            st.session_state.device_hours_on = suggestion["hours_on"]
            st.session_state.device_hours_idle = suggestion["hours_idle"]

    # Step 2: show suggestion note + editable fields + Add button
    if st.session_state.device_suggestion:
        note = st.session_state.device_suggestion.get("note", "")
        if note:
            st.markdown(
                f'<div style="font-size:0.75rem;color:#00D4FF;font-family:Space Mono,monospace;'
                f'margin:0.5rem 0;padding:0.6rem 1rem;background:#0D1520;border:1px solid #1E2A3A;'
                f'border-left:3px solid #00D4FF;border-radius:8px;">⚡ {note}</div>',
                unsafe_allow_html=True
            )

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        final_watts = st.number_input("Power (watts)", min_value=1, max_value=20000,
                                       value=st.session_state.device_watts, key="input_watts")
    with fc2:
        final_hours_on = st.number_input("Hours ON/day", min_value=0.0, max_value=24.0,
                                          value=float(st.session_state.device_hours_on), step=0.5, key="input_hours_on")
    with fc3:
        final_hours_idle = st.number_input("Hours Idle/day", min_value=0.0, max_value=24.0,
                                            value=float(st.session_state.device_hours_idle), step=0.5, key="input_hours_idle")

    add_name = st.session_state.get("device_search_name", "").strip() or search_name.strip()

    if st.button("⚡ Add Device", use_container_width=False):
        if not add_name:
            st.error("Search for a device first.")
        else:
            try:
                add_device_to_db(USER_ID, add_name,
                                  st.session_state.input_watts,
                                  st.session_state.input_hours_on,
                                  st.session_state.input_hours_idle)
                st.session_state.refresh_devices += 1
                st.session_state.device_suggestion = None
                st.session_state.device_search_name = ""
                st.session_state.device_watts = 100
                st.session_state.device_hours_on = 2.0
                st.session_state.device_hours_idle = 0.0
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to add device: {e}")

    if breakdown:
        st.markdown('<div class="section-header" style="margin-top:1.5rem;">Remove a Device <div class="section-line"></div></div>',
                    unsafe_allow_html=True)
        col_del1, col_del2 = st.columns([2, 1])
        with col_del1:
            to_delete = st.selectbox("Select device to remove", [item["device_name"] for item in breakdown])
        with col_del2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Remove"):
                try:
                    delete_device_from_db(USER_ID, to_delete)
                    st.session_state.refresh_devices += 1
                    st.success(f"Removed {to_delete}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to remove device: {e}")

# ── TAB 3: MONTHLY PROJECTION ──
with tab3:
    st.markdown('<div class="section-header">12-Month Cost Projection <div class="section-line"></div></div>',
                unsafe_allow_html=True)

    projection = computed["monthly_projection"]
    annual_total = round(sum(projection.values()), 2)
    annual_savings = round(annual_total * computed["optimization"]["potential_savings_percent"] / 100, 2)

    col_p1, col_p2 = st.columns([2.5, 1])
    with col_p1:
        if all(v == 0 for v in projection.values()):
            st.info("Add devices to see your monthly projection.")
        else:
            proj_df = pd.DataFrame({
                "Month": list(projection.keys()),
                "Cost ($)": list(projection.values()),
            })
            proj_df["Month"] = pd.Categorical(proj_df["Month"], categories=MONTH_NAMES, ordered=True)
            proj_df = proj_df.sort_values("Month").set_index("Month")
            st.line_chart(proj_df, color="#00D4FF", height=260)
            st.markdown(
                '<div style="font-size:0.65rem;color:#4A6080;font-family:Space Mono,monospace;margin-top:0.4rem;">'
                'Seasonal appliances (AC, heating) are only counted in their active months.</div>',
                unsafe_allow_html=True
            )

    with col_p2:
        peak_month = max(projection, key=projection.get) if any(v > 0 for v in projection.values()) else "—"
        peak_val = projection.get(peak_month, 0)
        st.markdown(f"""
<div class="metric-card">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Annual Total</div>
    <div style="font-family:Space Mono,monospace;font-size:1.8rem;color:#E8EDF5;margin-top:0.4rem;">${annual_total}</div>
</div>
<div class="metric-card" style="margin-top:1rem;">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Potential Annual Savings</div>
    <div style="font-family:Space Mono,monospace;font-size:1.8rem;color:#00FF94;margin-top:0.4rem;">${annual_savings}</div>
</div>
<div class="metric-card" style="margin-top:1rem;">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Peak Month</div>
    <div style="font-family:Space Mono,monospace;font-size:1.4rem;color:#FF6B35;margin-top:0.4rem;">{peak_month} — ${peak_val}</div>
</div>
""", unsafe_allow_html=True)

# ── TAB 4: AI ADVISOR ──
with tab4:
    st.markdown('<div class="section-header">AI Recommendations <div class="section-line"></div></div>',
                unsafe_allow_html=True)

    if not devices:
        st.info("Add devices first to get AI recommendations.")
    else:
        if st.button("⚡ Optimize My Usage"):
            with st.spinner("Analyzing your energy profile..."):
                result = generate_recommendation(devices, rates, computed)
                st.session_state.ai_result = result

        if st.session_state.ai_result:
            result = st.session_state.ai_result
            if "error" not in result:
                new_score = result.get("new_energy_score", power_score)
                monthly_savings = result.get("estimated_monthly_savings", 0)

                col_x, col_y = st.columns(2)
                with col_x:
                    st.markdown(f"""
<div class="metric-card">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Score After Optimizing</div>
    <div style="font-family:Space Mono,monospace;font-size:2rem;color:#00D4FF;margin-top:0.3rem;">{power_score} → {new_score}</div>
</div>
""", unsafe_allow_html=True)
                with col_y:
                    st.markdown(f"""
<div class="metric-card">
    <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Est. Monthly Savings</div>
    <div style="font-family:Space Mono,monospace;font-size:2rem;color:#00FF94;margin-top:0.3rem;">${monthly_savings}</div>
</div>
""", unsafe_allow_html=True)

                st.markdown('<div style="margin-top:1.5rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Recommendations</div>',
                            unsafe_allow_html=True)
                for rec in result.get("recommendations", []):
                    st.markdown(f'<div class="rec-card">→ {rec}</div>', unsafe_allow_html=True)

                st.markdown('<div style="margin-top:1rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Insights</div>',
                            unsafe_allow_html=True)
                for insight in result.get("insights", []):
                    st.markdown(f'<div class="insight-card">◆ {insight}</div>', unsafe_allow_html=True)
            else:
                st.error("AI response error. Check your Groq API key in secrets.")

# ── TAB 5: CHAT ──
with tab5:
    st.markdown('<div class="section-header">Chat with PowerPilot <div class="section-line"></div></div>',
                unsafe_allow_html=True)

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">⚡ {msg["content"]}</div>', unsafe_allow_html=True)

    question = st.text_input("Ask anything about your energy usage...", key="chat_input")
    if st.button("Send") and question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.spinner("Thinking..."):
            answer = ask_question(question, devices, rates, computed)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()
