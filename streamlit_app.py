import streamlit as st
import snowflake.connector
import json
import os
import requests
import pandas as pd
import uuid

st.set_page_config(page_title="PowerPilot", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# -----------------------------------------
# DEVICE DEFAULTS & SEASONAL LOGIC
# -----------------------------------------
DEVICE_DEFAULTS = {
    "refrigerator": (150, 24, 0), "fridge": (150, 24, 0), "freezer": (100, 24, 0),
    "microwave": (1200, 0.5, 0), "dishwasher": (1800, 1.5, 0), "oven": (2400, 1.0, 0),
    "stove": (1500, 1.0, 0), "coffee maker": (800, 0.5, 0), "toaster": (900, 0.2, 0),
    "kettle": (1500, 0.3, 0), "washer": (500, 1.0, 0), "washing machine": (500, 1.0, 0),
    "dryer": (5000, 1.0, 0), "led light": (10, 6, 0), "light": (60, 6, 0), "lamp": (60, 5, 0),
    "ceiling fan": (75, 6, 18), "tv": (100, 4, 20), "television": (100, 4, 20),
    "monitor": (30, 8, 16), "gaming pc": (400, 4, 20), "desktop": (300, 6, 18),
    "laptop": (60, 6, 18), "xbox": (120, 3, 21), "ps5": (200, 3, 21), "ps4": (140, 3, 21),
    "nintendo switch": (18, 3, 21), "router": (10, 24, 0), "modem": (10, 24, 0),
    "air conditioner": (1500, 8, 16), "ac": (1500, 8, 16), "window ac": (1200, 8, 16),
    "central ac": (3500, 8, 16), "heater": (1500, 8, 16), "space heater": (1500, 8, 16),
    "furnace": (600, 8, 16), "heat pump": (1000, 8, 16), "water heater": (4000, 3, 21),
    "vacuum": (1400, 0.5, 0), "hair dryer": (1875, 0.3, 0), "phone charger": (5, 8, 16),
    "dehumidifier": (280, 6, 18), "humidifier": (50, 8, 16), "pool pump": (1500, 8, 16),
    "hot tub": (3000, 2, 22), "security camera": (15, 24, 0), "smart speaker": (3, 24, 0),
    "printer": (30, 0.5, 0),
}

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
COOLING_KEYWORDS = ["ac", "air conditioner", "air conditioning", "central air", "window ac", "mini split", "cooler"]
HEATING_KEYWORDS = ["heat", "heater", "heating", "furnace", "boiler", "heat pump", "space heater"]


def get_active_months(name: str):
    key = name.strip().lower()
    if any(k in key for k in COOLING_KEYWORDS):
        return [6, 7, 8, 9]
    if any(k in key for k in HEATING_KEYWORDS):
        return [11, 12, 1, 2, 3]
    if "pool pump" in key:
        return [5, 6, 7, 8, 9]
    return list(range(1, 13))


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
.metric-accent { color: #00D4FF; } .metric-accent-green { color: #00FF94; } .metric-accent-orange { color: #FF6B35; }
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
.rate-source-badge { display: inline-block; font-size: 0.65rem; font-family: 'Space Mono', monospace; padding: 3px 9px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.08em; }
.rate-source-live { background: #0A2A1A; color: #00FF94; border: 1px solid #00FF9444; }
.rate-source-fallback { background: #2A1A0A; color: #FF6B35; border: 1px solid #FF6B3544; }
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
# -----------------------------------------
def _sf_conn(autocommit=False):
    creds = dict(
        account=st.secrets["SNOWFLAKE_ACCOUNT"],
        user=st.secrets["SNOWFLAKE_USER"],
        password=st.secrets["SNOWFLAKE_PASSWORD"],
        database="POWERPILOT",
        schema="MAIN",
    )
    if autocommit:
        creds["autocommit"] = True
    return snowflake.connector.connect(**creds)


def run_query(query, params=None):
    conn = _sf_conn()
    cur = conn.cursor()
    try:
        cur.execute(query, params) if params else cur.execute(query)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        df.columns = [c.upper() for c in df.columns]
        return df
    finally:
        cur.close(); conn.close()


def run_write(query, params=None):
    conn = _sf_conn(autocommit=True)
    cur = conn.cursor()
    try:
        cur.execute(query, params) if params else cur.execute(query)
    finally:
        cur.close(); conn.close()


# -----------------------------------------
# SCHEMA DETECTION
# -----------------------------------------
@st.cache_data(ttl=300)
def get_users_columns():
    try:
        df = run_query("SELECT * FROM POWERPILOT.MAIN.users WHERE 1=0")
        return list(df.columns)
    except Exception:
        return ["USER_ID", "ZIP_CODE"]


def has_name_col():
    return "NAME" in get_users_columns()


# -----------------------------------------
# USERS
# -----------------------------------------
def get_all_users():
    try:
        if has_name_col():
            df = run_query("SELECT user_id, name, zip_code FROM POWERPILOT.MAIN.users ORDER BY user_id")
        else:
            df = run_query("SELECT user_id, zip_code FROM POWERPILOT.MAIN.users ORDER BY user_id")
            df["NAME"] = df["USER_ID"]
        return df.to_dict(orient="records")
    except Exception:
        return []


def create_user(user_id, name, zip_code):
    if has_name_col():
        run_write(
            "INSERT INTO POWERPILOT.MAIN.users (user_id, name, zip_code) VALUES (%s, %s, %s)",
            params=(user_id, name, zip_code))
    else:
        run_write(
            "INSERT INTO POWERPILOT.MAIN.users (user_id, zip_code) VALUES (%s, %s)",
            params=(user_id, zip_code))


def update_user_zip(user_id, zip_code):
    run_write(
        "UPDATE POWERPILOT.MAIN.users SET zip_code = %s WHERE user_id = %s",
        params=(zip_code, user_id))


# -----------------------------------------
# DEVICES
# -----------------------------------------
def get_devices(user_id):
    df = run_query(
        "SELECT device_name, power_on_watts, power_idle_watts, hours_on_per_day, hours_idle_per_day "
        "FROM POWERPILOT.MAIN.devices WHERE user_id = %s", params=(user_id,))
    devices = []
    for _, row in df.iterrows():
        def safe(val, default=0):
            try:
                f = float(val)
                return f if f == f else default
            except (TypeError, ValueError):
                return default
        d = {
            "device_name": str(row["DEVICE_NAME"]),
            "power_on_watts": safe(row["POWER_ON_WATTS"]),
            "hours_on_per_day": safe(row["HOURS_ON_PER_DAY"]),
            "hours_idle_per_day": safe(row["HOURS_IDLE_PER_DAY"]),
        }
        idle = safe(row["POWER_IDLE_WATTS"], default=None)
        if idle is not None:
            d["power_idle_watts"] = idle
        devices.append(d)
    return devices


def add_device_to_db(user_id, device_name, power_on_watts, hours_on, hours_idle):
    idle_watts = round(float(power_on_watts) * 0.05, 2)
    run_write(
        "INSERT INTO POWERPILOT.MAIN.devices "
        "(user_id, device_name, power_on_watts, power_idle_watts, hours_on_per_day, hours_idle_per_day) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        params=(user_id, device_name, float(power_on_watts), idle_watts, float(hours_on), float(hours_idle)))


def delete_device_from_db(user_id, device_name):
    run_write(
        "DELETE FROM POWERPILOT.MAIN.devices WHERE user_id = %s AND device_name = %s",
        params=(user_id, device_name))


# -----------------------------------------
# OPENEI RATES
# -----------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_rates_openei(zip_code):
    key = st.secrets.get("OPENEI_API_KEY") or os.environ.get("OPENEI_API_KEY")
    if not key:
        return _flat_to_tou(0.13), "fallback"
    try:
        resp = requests.get(
            "https://api.openei.org/utility_rates",
            params={"version": 8, "api_key": key, "format": "json", "address": zip_code, "limit": 1, "detail": "full"},
            timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return _flat_to_tou(0.13), "fallback"
        parsed = _parse_tou(items[0])
        if parsed and len(parsed) == 24:
            return parsed, "live"
        return _flat_to_tou(0.13), "fallback"
    except Exception:
        return _flat_to_tou(0.13), "fallback"


def _parse_tou(rate):
    ers = rate.get("energyratestructure", [])
    sch = rate.get("energyweekdayschedule", [])
    if ers and sch:
        hour_rates = {}
        periods = sch[0] if sch else []
        for h, p_idx in enumerate(periods):
            try:
                tier = ers[p_idx][0]
                hour_rates[h] = round(tier.get("rate", 0) + tier.get("adj", 0), 4)
            except (IndexError, KeyError, TypeError):
                hour_rates[h] = 0.13
        return [{"hour": h, "cost_per_kwh": hour_rates.get(h, 0.13)} for h in range(24)]
    flat = 0.13
    try:
        flat = rate["energyratestructure"][0][0]["rate"]
    except (KeyError, IndexError, TypeError):
        pass
    return _flat_to_tou(flat)


def _flat_to_tou(base):
    mults = [(range(0, 6), 0.80), (range(6, 9), 1.10), (range(9, 16), 1.20),
             (range(16, 21), 1.50), (range(21, 24), 0.90)]
    out = []
    for h in range(24):
        m = next((x for r, x in mults if h in r), 1.0)
        out.append({"hour": h, "cost_per_kwh": round(base * m, 4)})
    return out


# -----------------------------------------
# OPTIMIZER
# -----------------------------------------
def compute_energy_results(devices, rates):
    sorted_r = sorted(rates, key=lambda r: r["cost_per_kwh"]) if rates else []
    best_h = [r["hour"] for r in sorted_r[:6]]
    worst_h = [r["hour"] for r in sorted_r[-3:]]
    cheap = sorted_r[0]["cost_per_kwh"] if sorted_r else 0.12
    pricey = sorted_r[-1]["cost_per_kwh"] if sorted_r else 0.12
    savings_pct = round((1 - cheap / pricey) * 100) if pricey else 0

    if not devices:
        return {
            "summary": {"total_kwh_per_day": 0, "total_cost_per_month": 0},
            "breakdown": [],
            "optimization": {"best_hours": best_h, "worst_hours": worst_h,
                             "potential_savings_percent": savings_pct, "potential_monthly_savings_dollars": 0},
            "phantom_load": {"total_watts": 0, "daily_kwh": 0, "percentage_of_total": 0},
            "power_score": 0,
            "monthly_projection": {m: 0 for m in MONTH_NAMES},
        }

    avg_rate = sum(r["cost_per_kwh"] for r in rates) / len(rates) if rates else 0.12
    breakdown = []
    total_kwh = 0.0
    for d in devices:
        on_w = d.get("power_on_watts", 0)
        idle_w = d.get("power_idle_watts", on_w * 0.05)
        h_on = d.get("hours_on_per_day", 0)
        h_idle = d.get("hours_idle_per_day", 0)
        kwh = (on_w * h_on + idle_w * h_idle) / 1000
        total_kwh += kwh
        breakdown.append({"device_name": d["device_name"], "kwh_per_day": round(kwh, 3),
                          "cost_per_month": round(kwh * 30 * avg_rate, 2)})

    total_cost = round(total_kwh * 30 * avg_rate, 2)
    pot_save = round(total_cost * savings_pct / 100, 2)
    phantom_w = sum(d.get("power_on_watts", 0) * 0.05 * d.get("hours_idle_per_day", 0) for d in devices)
    phantom_kwh = round(phantom_w / 1000, 3)
    phantom_pct = round(phantom_kwh / total_kwh * 100) if total_kwh else 0

    total_on = sum(d.get("hours_on_per_day", 0) for d in devices)
    peak_pen = round(min(30, (len(set(worst_h)) / 24) * total_on * 5))
    ineff_pen = round(min(30, phantom_pct * 0.6))
    off_bonus = round(min(20, savings_pct * 0.2))
    score = max(0, min(100, 100 - peak_pen - ineff_pen + off_bonus))

    projection = {}
    for i, mname in enumerate(MONTH_NAMES):
        mnum = i + 1
        mkwh = 0.0
        for d in devices:
            if mnum not in get_active_months(d["device_name"]):
                continue
            on_w = d.get("power_on_watts", 0)
            idle_w = d.get("power_idle_watts", on_w * 0.05)
            mkwh += (on_w * d.get("hours_on_per_day", 0) + idle_w * d.get("hours_idle_per_day", 0)) / 1000
        projection[mname] = round(mkwh * 30 * avg_rate, 2)

    return {
        "summary": {"total_kwh_per_day": round(total_kwh, 3), "total_cost_per_month": total_cost},
        "breakdown": breakdown,
        "optimization": {"best_hours": best_h, "worst_hours": worst_h,
                         "potential_savings_percent": savings_pct, "potential_monthly_savings_dollars": pot_save},
        "phantom_load": {"total_watts": round(phantom_w, 1), "daily_kwh": phantom_kwh, "percentage_of_total": phantom_pct},
        "power_score": score,
        "monthly_projection": projection,
    }


# -----------------------------------------
# AI
# -----------------------------------------
def call_groq(prompt, max_tokens=1024):
    key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]}, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def generate_recommendation(devices, rates, computed):
    ps = computed.get("power_score", 50)
    prompt = f"""You are an energy optimization AI. Analyze this data and return recommendations.
Devices: {json.dumps(devices)}
Rates: {json.dumps(rates)}
Summary: {json.dumps(computed)}
PowerScore: {ps}/100.
Return ONLY JSON:
{{"current_energy_score":{ps},"new_energy_score":<int higher than {ps} max 100>,"recommendations":["<tip>","<tip>","<tip>"],"estimated_monthly_savings":<float>,"insights":["<insight>","<insight>"],"best_usage_hours":[<ints>],"worst_usage_hours":[<ints>]}}"""
    raw = call_groq(prompt, 1024)
    try:
        if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception:
        return {"error": "Failed to parse AI response"}


def ask_question(question, devices, rates, computed):
    prompt = f"""You are PowerPilot, a friendly home energy advisor.
Devices: {json.dumps(devices)}
Rates: {json.dumps(rates)}
Summary: {json.dumps(computed)}
User asks: "{question}"
Answer in 2-4 sentences. Be specific, friendly, practical."""
    return call_groq(prompt, 512)


def lookup_device_specs(name):
    key = name.strip().lower()
    if key in DEVICE_DEFAULTS:
        w, on, idle = DEVICE_DEFAULTS[key]
        return {"watts": w, "hours_on": float(on), "hours_idle": float(idle), "note": ""}
    for k, v in DEVICE_DEFAULTS.items():
        if k in key or key in k:
            w, on, idle = v
            return {"watts": w, "hours_on": float(on), "hours_idle": float(idle), "note": ""}
    try:
        prompt = f"""For "{name}", return ONLY JSON: {{"watts":<int typical running wattage>,"hours_on":<float daily hours actively running>,"hours_idle":<float standby hours>,"note":"<one-sentence energy fact>"}} Rules: Lights have hours_idle=0. TV: 4h on, 18h standby. Base on US averages."""
        raw = call_groq(prompt, 200).strip()
        if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
        res = json.loads(raw)
        return {"watts": max(1, int(float(res.get("watts", 100)))),
                "hours_on": min(24.0, max(0.0, float(res.get("hours_on", 2.0)))),
                "hours_idle": min(24.0, max(0.0, float(res.get("hours_idle", 0.0)))),
                "note": str(res.get("note", ""))}
    except Exception:
        return {"watts": 100, "hours_on": 2.0, "hours_idle": 0.0, "note": ""}


# -----------------------------------------
# SESSION STATE
# -----------------------------------------
for k, v in {"chat_history": [], "ai_result": None, "refresh_devices": 0,
             "device_lookup_result": None, "active_user_id": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def _uid(u): return u.get("USER_ID", "")
def _uname(u): return u.get("NAME") or u.get("USER_ID", "")
def _uzip(u): return u.get("ZIP_CODE", "") or ""


# -----------------------------------------
# SIDEBAR
# -----------------------------------------
with st.sidebar:
    st.markdown("""<div style="font-family:'Syne',sans-serif;font-weight:800;font-size:1.3rem;color:#00D4FF;letter-spacing:-0.02em;padding-bottom:0.5rem;border-bottom:1px solid #1E2A3A;margin-bottom:1rem;">⚡ PowerPilot</div><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.12em;font-family:'Space Mono',monospace;margin-bottom:0.8rem;">User Profile</div>""", unsafe_allow_html=True)

    all_users = get_all_users()

    if all_users:
        opts = {f"{_uname(u)} ({_uid(u)})": _uid(u) for u in all_users}
        names = list(opts.keys())
        idx = 0
        if st.session_state.active_user_id:
            for i, uid in enumerate(opts.values()):
                if uid == st.session_state.active_user_id:
                    idx = i; break
        sel_label = st.selectbox("Select profile", names, index=idx, key="user_select")
        sel_uid = opts[sel_label]

        if sel_uid != st.session_state.active_user_id:
            st.session_state.active_user_id = sel_uid
            st.session_state.chat_history = []
            st.session_state.ai_result = None
            st.session_state.refresh_devices += 1

        udata = next((u for u in all_users if _uid(u) == sel_uid), None)
        if udata:
            cur_zip = _uzip(udata)
            st.markdown(f'<div style="font-size:0.72rem;color:#4A6080;font-family:Space Mono,monospace;margin-top:0.2rem;">📍 ZIP: {cur_zip or "not set"}</div>', unsafe_allow_html=True)
            with st.expander("✏️ Edit ZIP code"):
                new_zip = st.text_input("ZIP code", value=cur_zip or "", max_chars=10, key="edit_zip")
                if st.button("Save ZIP", key="save_zip"):
                    if new_zip.strip():
                        try:
                            update_user_zip(sel_uid, new_zip.strip())
                            get_rates_openei.clear()
                            st.success("ZIP updated!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
    else:
        st.info("No profiles found. Create one below.")

    st.markdown("<hr style='border-color:#1E2A3A;margin:1rem 0;'>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.12em;font-family:Space Mono,monospace;margin-bottom:0.6rem;">+ New Profile</div>', unsafe_allow_html=True)

    with st.form("new_user_form", clear_on_submit=True):
        label = "Your name" if has_name_col() else "Profile ID"
        new_name = st.text_input(label, placeholder="e.g. home_alex")
        new_zip_in = st.text_input("ZIP code", placeholder="e.g. 13037", max_chars=10)
        if st.form_submit_button("Create Profile"):
            if not new_name.strip():
                st.error("Name is required.")
            elif not new_zip_in.strip():
                st.error("ZIP code is required.")
            else:
                try:
                    new_uid = "u" + uuid.uuid4().hex[:8] if has_name_col() else new_name.strip().lower().replace(" ", "_")[:30]
                    create_user(new_uid, new_name.strip(), new_zip_in.strip())
                    st.session_state.active_user_id = new_uid
                    st.session_state.chat_history = []
                    st.session_state.ai_result = None
                    st.session_state.refresh_devices += 1
                    get_users_columns.clear()
                    st.success(f"Profile created: {new_name.strip()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not create profile: {e}")

    if not st.session_state.active_user_id and all_users:
        st.session_state.active_user_id = _uid(all_users[0])

USER_ID = st.session_state.active_user_id

if not USER_ID:
    st.warning("👈 Create a profile in the sidebar to get started.")
    st.stop()

# -----------------------------------------
# LOAD DATA
# -----------------------------------------
_active = next((u for u in get_all_users() if _uid(u) == USER_ID), None)
user_zip = _uzip(_active) if _active else "10001"
if not user_zip: user_zip = "10001"

with st.spinner("Loading your energy profile..."):
    _ = st.session_state.refresh_devices
    devices = get_devices(USER_ID)
    rates, rate_source = get_rates_openei(user_zip)

computed = compute_energy_results(devices, rates)
_display_name = _uname(_active) if _active else USER_ID

# -----------------------------------------
# HEADER
# -----------------------------------------
st.markdown(f"""<div class="pilot-header"><div class="pilot-logo">⚡</div><div><div class="pilot-title">PowerPilot</div><div class="pilot-tagline">Most people think saving energy means using less. When you use it matters just as much.</div></div><div style="margin-left:auto;text-align:right;"><div style="font-family:'Space Mono',monospace;font-size:0.72rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;">Viewing profile</div><div style="font-family:'Syne',sans-serif;font-weight:700;font-size:1rem;color:#E8EDF5;">{_display_name}</div></div></div>""", unsafe_allow_html=True)

src_class = "rate-source-live" if rate_source == "live" else "rate-source-fallback"
src_label = f"Live OpenEI Rates — ZIP {user_zip}" if rate_source == "live" else f"Estimated Rates — ZIP {user_zip}"
st.markdown(f'<div style="margin:0.5rem 0;"><span class="rate-source-badge {src_class}">{src_label}</span></div>', unsafe_allow_html=True)

# -----------------------------------------
# TOP METRICS
# -----------------------------------------
ps = computed["power_score"]
tk = computed["summary"]["total_kwh_per_day"]
tc = computed["summary"]["total_cost_per_month"]
pot = computed["optimization"]["potential_monthly_savings_dollars"]
php = computed["phantom_load"]["percentage_of_total"]
ac = round(tc * 12, 2)

c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 1])
with c1:
    st.markdown(f'<div class="score-ring-wrap"><div class="score-number">{ps}</div><div class="score-label">PowerScore</div><div class="score-bar-bg"><div class="score-bar-fill" style="--target-width:{ps}%;width:{ps}%"></div></div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="metric-card"><div class="metric-value metric-accent">{tk}<span class="metric-unit"> kWh</span></div><div class="metric-label">Daily Usage</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="metric-card"><div class="metric-value">${tc}<span class="metric-unit">/mo</span></div><div class="metric-label">Est. Monthly Cost</div><div class="metric-sub">${ac}/yr</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="metric-card"><div class="metric-value metric-accent-green">${pot}<span class="metric-unit">/mo</span></div><div class="metric-label">Potential Savings</div><div class="metric-sub">${round(pot*12,2)}/yr</div></div>', unsafe_allow_html=True)
with c5:
    st.markdown(f'<div class="metric-card"><div class="metric-value metric-accent-orange">{php}<span class="metric-unit">%</span></div><div class="metric-label">Phantom Load</div><div class="metric-sub">idle device waste</div></div>', unsafe_allow_html=True)

# -----------------------------------------
# TABS
# -----------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["⚡ Rates & Hours", "📊 Devices", "📈 Projection", "🤖 AI Advisor", "💬 Chat"])

with tab1:
    st.markdown('<div class="section-header">Time-of-Use Rates <div class="section-line"></div></div>', unsafe_allow_html=True)
    bh = set(computed["optimization"]["best_hours"])
    wh = set(computed["optimization"]["worst_hours"])
    rmap = {r["hour"]: r["cost_per_kwh"] for r in rates}
    mx = max(rmap.values()) if rmap else 0.25
    mn = min(rmap.values()) if rmap else 0.10
    bars = '<div style="display:grid;grid-template-columns:repeat(24,1fr);gap:3px;align-items:end;height:100px;">'
    for h in range(24):
        r = rmap.get(h, 0.12)
        hp = int(((r - mn) / (mx - mn + 0.001)) * 75 + 25)
        col = "#FF3366" if h in wh else ("#00FF94" if h in bh else "#1E3A5F")
        bars += f'<div class="hour-bar-wrap"><div class="hour-tooltip">{h:02d}:00 — ${r:.4f}/kWh</div><div class="hour-bar" style="background:{col};height:{hp}%;"></div></div>'
    bars += "</div>"
    labels = '<div style="display:grid;grid-template-columns:repeat(24,1fr);gap:3px;margin-top:4px;">' + "".join(f'<div class="hour-label">{h:02d}</div>' for h in range(24)) + "</div>"
    st.markdown(f'<div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;padding:1.5rem;"><div style="display:flex;justify-content:space-between;margin-bottom:0.8rem;"><span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;">HOUR OF DAY — hover for rate</span><span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;"><span style="color:#00FF94;">■</span> Cheapest &nbsp;<span style="color:#FF3366;">■</span> Most Expensive &nbsp;<span style="color:#1E3A5F;">■</span> Mid</span></div>{bars}{labels}</div>', unsafe_allow_html=True)

    ca, cb = st.columns(2)
    with ca:
        st.markdown(f'<div class="metric-card" style="margin-top:1rem;"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Best Hours to Run Devices</div><div style="font-family:Space Mono,monospace;font-size:1.1rem;color:#00FF94;margin-top:0.5rem;">{", ".join(f"{h:02d}:00" for h in sorted(bh)) or "—"}</div></div>', unsafe_allow_html=True)
    with cb:
        st.markdown(f'<div class="metric-card" style="margin-top:1rem;"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Avoid These Hours</div><div style="font-family:Space Mono,monospace;font-size:1.1rem;color:#FF3366;margin-top:0.5rem;">{", ".join(f"{h:02d}:00" for h in sorted(wh)) or "—"}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top:2rem;">Hidden Energy Waste <div class="section-line"></div></div>', unsafe_allow_html=True)
    pw = computed["phantom_load"]["total_watts"]
    pk = computed["phantom_load"]["daily_kwh"]
    st.markdown(f'<div class="metric-card"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Phantom Load</div><div style="font-family:Space Mono,monospace;font-size:1.5rem;color:#FF6B35;margin-top:0.3rem;">{php}% of total usage</div><div style="font-size:0.8rem;color:#4A6080;margin-top:0.3rem;">{pw}W idle draw · {pk} kWh/day wasted</div><div class="phantom-bar-bg"><div class="phantom-bar-fill" style="width:{min(php,100)}%"></div></div></div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="section-header">Device Breakdown <div class="section-line"></div></div>', unsafe_allow_html=True)
    bd = computed["breakdown"]
    if not bd:
        st.info("No devices added yet. Add your first device below.")
    else:
        st.markdown('<div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;overflow:hidden;"><div class="device-row device-row-header"><div>Device</div><div>kWh/day</div><div>Cost/month</div><div>Share</div></div>', unsafe_allow_html=True)
        for item in bd:
            sh = round(item["kwh_per_day"] / tk * 100) if tk else 0
            st.markdown(f'<div class="device-row"><div class="device-name">{item["device_name"]}</div><div class="device-val">{item["kwh_per_day"]}</div><div class="device-cost">${item["cost_per_month"]}</div><div class="device-val">{sh}%</div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top:2rem;">Add a Device <div class="section-line"></div></div>', unsafe_allow_html=True)
    s1, s2 = st.columns([3, 1])
    with s1:
        srch = st.text_input("Device Name", placeholder="e.g. Refrigerator, AC, LED Lights...", key="dev_srch")
    with s2:
        st.markdown("<br>", unsafe_allow_html=True)
        do_srch = st.button("🔍 Search", use_container_width=True, key="btn_srch")

    if do_srch:
        if not srch.strip():
            st.warning("Enter a device name to search.")
        else:
            with st.spinner("Looking up specs..."):
                res = lookup_device_specs(srch.strip())
            res["name"] = srch.strip()
            st.session_state.device_lookup_result = res

    lr = st.session_state.device_lookup_result
    if lr:
        if lr.get("note"):
            st.markdown(f'<div style="font-size:0.75rem;color:#00D4FF;font-family:Space Mono,monospace;margin:0.6rem 0;padding:0.6rem 1rem;background:#0D1520;border:1px solid #1E2A3A;border-left:3px solid #00D4FF;border-radius:8px;">⚡ {lr["note"]}</div>', unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        with f1:
            ew = st.number_input("Power (watts)", min_value=1, max_value=20000, value=int(lr["watts"]), key="ew")
        with f2:
            eon = st.number_input("Hours ON/day", min_value=0.0, max_value=24.0, value=float(lr["hours_on"]), step=0.5, key="eon")
        with f3:
            ei = st.number_input("Hours Idle/day", min_value=0.0, max_value=24.0, value=float(lr["hours_idle"]), step=0.5, key="ei")

        if st.button(f"⚡ Add {lr['name']} to my home", key="add_dev"):
            try:
                add_device_to_db(USER_ID, lr["name"], ew, eon, ei)
                st.session_state.refresh_devices += 1
                st.session_state.device_lookup_result = None
                st.success(f"Added {lr['name']}!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed: {e}")
    else:
        st.caption("Search for a device above to auto-fill its average energy specs.")

    if bd:
        st.markdown('<div class="section-header" style="margin-top:1.5rem;">Remove a Device <div class="section-line"></div></div>', unsafe_allow_html=True)
        d1, d2 = st.columns([2, 1])
        with d1:
            td = st.selectbox("Select device to remove", [i["device_name"] for i in bd])
        with d2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Remove"):
                try:
                    delete_device_from_db(USER_ID, td)
                    st.session_state.refresh_devices += 1
                    st.success(f"Removed {td}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed: {e}")

with tab3:
    st.markdown('<div class="section-header">12-Month Cost Projection <div class="section-line"></div></div>', unsafe_allow_html=True)
    proj = computed["monthly_projection"]
    at = round(sum(proj.values()), 2)
    ast_ = round(at * computed["optimization"]["potential_savings_percent"] / 100, 2)

    p1, p2 = st.columns([2.5, 1])
    with p1:
        if all(v == 0 for v in proj.values()):
            st.info("Add devices to see your monthly projection.")
        else:
            pdf = pd.DataFrame({"Month": list(proj.keys()), "Cost ($)": list(proj.values())})
            pdf["Month"] = pd.Categorical(pdf["Month"], categories=MONTH_NAMES, ordered=True)
            pdf = pdf.sort_values("Month").set_index("Month")
            st.line_chart(pdf, color="#00D4FF", height=260)
            st.markdown('<div style="font-size:0.65rem;color:#4A6080;font-family:Space Mono,monospace;margin-top:0.4rem;">Seasonal appliances (AC, heating) are only counted in their active months.</div>', unsafe_allow_html=True)
    with p2:
        pm = max(proj, key=proj.get) if any(v > 0 for v in proj.values()) else "—"
        pv = proj.get(pm, 0)
        st.markdown(f'<div class="metric-card"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Annual Total</div><div style="font-family:Space Mono,monospace;font-size:1.8rem;color:#E8EDF5;margin-top:0.4rem;">${at}</div></div><div class="metric-card" style="margin-top:1rem;"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Potential Annual Savings</div><div style="font-family:Space Mono,monospace;font-size:1.8rem;color:#00FF94;margin-top:0.4rem;">${ast_}</div></div><div class="metric-card" style="margin-top:1rem;"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Peak Month</div><div style="font-family:Space Mono,monospace;font-size:1.4rem;color:#FF6B35;margin-top:0.4rem;">{pm} — ${pv}</div></div>', unsafe_allow_html=True)

with tab4:
    st.markdown('<div class="section-header">AI Recommendations <div class="section-line"></div></div>', unsafe_allow_html=True)
    if not devices:
        st.info("Add devices first to get AI recommendations.")
    else:
        if st.button("⚡ Optimize My Usage"):
            with st.spinner("Analyzing..."):
                st.session_state.ai_result = generate_recommendation(devices, rates, computed)

        if st.session_state.ai_result:
            res = st.session_state.ai_result
            if "error" not in res:
                ns = res.get("new_energy_score", ps)
                ms = res.get("estimated_monthly_savings", 0)
                x, y = st.columns(2)
                with x:
                    st.markdown(f'<div class="metric-card"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Score After Optimizing</div><div style="font-family:Space Mono,monospace;font-size:2rem;color:#00D4FF;margin-top:0.3rem;">{ps} → {ns}</div></div>', unsafe_allow_html=True)
                with y:
                    st.markdown(f'<div class="metric-card"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Est. Monthly Savings</div><div style="font-family:Space Mono,monospace;font-size:2rem;color:#00FF94;margin-top:0.3rem;">${ms}</div></div>', unsafe_allow_html=True)
                st.markdown('<div style="margin-top:1.5rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Recommendations</div>', unsafe_allow_html=True)
                for r in res.get("recommendations", []):
                    st.markdown(f'<div class="rec-card">→ {r}</div>', unsafe_allow_html=True)
                st.markdown('<div style="margin-top:1rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Insights</div>', unsafe_allow_html=True)
                for ins in res.get("insights", []):
                    st.markdown(f'<div class="insight-card">◆ {ins}</div>', unsafe_allow_html=True)
            else:
                st.error("AI response error.")

with tab5:
    st.markdown('<div class="section-header">Chat with PowerPilot <div class="section-line"></div></div>', unsafe_allow_html=True)
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">⚡ {msg["content"]}</div>', unsafe_allow_html=True)
    q = st.text_input("Ask anything about your energy usage...", key="chat_input")
    if st.button("Send") and q:
        st.session_state.chat_history.append({"role": "user", "content": q})
        with st.spinner("Thinking..."):
            a = ask_question(q, devices, rates, computed)
        st.session_state.chat_history.append({"role": "assistant", "content": a})
        st.rerun()
