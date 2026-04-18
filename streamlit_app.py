import streamlit as st
import snowflake.connector
import json
import os
import requests

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="PowerPilot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    background-color: #080C12;
    color: #E8EDF5;
    font-family: 'Syne', sans-serif;
}

.main { background-color: #080C12; }

/* Header */
.pilot-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 2rem 0 1rem 0;
    border-bottom: 1px solid #1E2A3A;
    margin-bottom: 2rem;
}
.pilot-logo {
    font-size: 2.4rem;
}
.pilot-title {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 2rem;
    color: #00D4FF;
    letter-spacing: -0.02em;
    margin: 0;
}
.pilot-sub {
    font-size: 0.85rem;
    color: #4A6080;
    margin: 0;
    font-family: 'Space Mono', monospace;
}

/* PowerScore */
.score-ring-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    background: linear-gradient(135deg, #0D1520 0%, #111C2E 100%);
    border: 1px solid #1E2A3A;
    border-radius: 16px;
}
.score-number {
    font-family: 'Space Mono', monospace;
    font-size: 4rem;
    font-weight: 700;
    color: #00D4FF;
    line-height: 1;
}
.score-label {
    font-size: 0.75rem;
    color: #4A6080;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 0.4rem;
    font-family: 'Space Mono', monospace;
}
.score-bar-bg {
    width: 100%;
    height: 6px;
    background: #1E2A3A;
    border-radius: 3px;
    margin-top: 1rem;
}
.score-bar-fill {
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(90deg, #0066FF, #00D4FF);
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #0D1520 0%, #111C2E 100%);
    border: 1px solid #1E2A3A;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    height: 100%;
}
.metric-value {
    font-family: 'Space Mono', monospace;
    font-size: 2rem;
    font-weight: 700;
    color: #E8EDF5;
    line-height: 1.1;
}
.metric-unit {
    font-size: 0.85rem;
    color: #4A6080;
    font-family: 'Space Mono', monospace;
}
.metric-label {
    font-size: 0.75rem;
    color: #4A6080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.3rem;
}
.metric-accent {
    color: #00D4FF;
}
.metric-accent-green {
    color: #00FF94;
}
.metric-accent-orange {
    color: #FF6B35;
}

/* Section headers */
.section-header {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 1rem;
    color: #4A6080;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 2rem 0 1rem 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-line {
    flex: 1;
    height: 1px;
    background: #1E2A3A;
}

/* Hour chart */
.hour-grid {
    display: grid;
    grid-template-columns: repeat(24, 1fr);
    gap: 3px;
    margin: 0.5rem 0;
}
.hour-cell {
    height: 40px;
    border-radius: 4px;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    padding-bottom: 3px;
    font-size: 0.45rem;
    font-family: 'Space Mono', monospace;
    color: #4A6080;
    position: relative;
}
.hour-label-row {
    display: grid;
    grid-template-columns: repeat(24, 1fr);
    gap: 3px;
    margin-bottom: 0.5rem;
}
.hour-label {
    font-size: 0.5rem;
    font-family: 'Space Mono', monospace;
    color: #4A6080;
    text-align: center;
}

/* Device table */
.device-row {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr;
    padding: 0.8rem 1rem;
    border-bottom: 1px solid #1E2A3A;
    align-items: center;
}
.device-row:last-child { border-bottom: none; }
.device-row-header {
    font-size: 0.7rem;
    color: #4A6080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-family: 'Space Mono', monospace;
}
.device-name {
    font-weight: 600;
    color: #E8EDF5;
}
.device-val {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: #A0B4CC;
}
.device-cost {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: #00FF94;
}

/* Recommendation cards */
.rec-card {
    background: #0D1520;
    border: 1px solid #1E2A3A;
    border-left: 3px solid #00D4FF;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    font-size: 0.9rem;
    color: #C0D0E0;
    line-height: 1.5;
}
.insight-card {
    background: #0D1520;
    border: 1px solid #1E2A3A;
    border-left: 3px solid #00FF94;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.6rem;
    font-size: 0.9rem;
    color: #C0D0E0;
    line-height: 1.5;
}

/* Phantom load */
.phantom-bar-bg {
    width: 100%;
    height: 8px;
    background: #1E2A3A;
    border-radius: 4px;
    margin-top: 0.5rem;
}
.phantom-bar-fill {
    height: 8px;
    border-radius: 4px;
    background: linear-gradient(90deg, #FF6B35, #FF3366);
}

/* Chat */
.chat-bubble-user {
    background: #1E2A3A;
    border-radius: 12px 12px 2px 12px;
    padding: 0.8rem 1.1rem;
    margin: 0.5rem 0;
    font-size: 0.9rem;
    color: #E8EDF5;
    max-width: 80%;
    margin-left: auto;
}
.chat-bubble-ai {
    background: #0D1A2E;
    border: 1px solid #1E2A3A;
    border-radius: 12px 12px 12px 2px;
    padding: 0.8rem 1.1rem;
    margin: 0.5rem 0;
    font-size: 0.9rem;
    color: #C0D0E0;
    max-width: 80%;
    line-height: 1.5;
}

/* Streamlit overrides */
.stButton > button {
    background: linear-gradient(135deg, #0066FF, #00D4FF);
    color: #080C12;
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.5rem;
    font-size: 0.9rem;
    letter-spacing: 0.05em;
}
.stButton > button:hover {
    opacity: 0.85;
}
.stTextInput > div > div > input {
    background: #0D1520;
    border: 1px solid #1E2A3A;
    border-radius: 8px;
    color: #E8EDF5;
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
}
.stSelectbox > div > div {
    background: #0D1520;
    border: 1px solid #1E2A3A;
    border-radius: 8px;
    color: #E8EDF5;
}
div[data-testid="stTab"] button {
    font-family: 'Syne', sans-serif;
    font-weight: 600;
    color: #4A6080;
}
div[data-testid="stTab"] button[aria-selected="true"] {
    color: #00D4FF;
    border-bottom-color: #00D4FF;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# SNOWFLAKE CONNECTION
# Uses Streamlit in Snowflake native connection
# ─────────────────────────────────────────
@st.cache_resource
def get_snowflake_connection():
    return snowflake.connector.connect(
        account=st.secrets["SNOWFLAKE_ACCOUNT"],
        user=st.secrets["SNOWFLAKE_USER"],
        password=st.secrets["SNOWFLAKE_PASSWORD"],
        database="POWERPILOT",
        schema="MAIN",
    )

def run_query(query, params=None):
    import pandas as pd
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    return pd.DataFrame(rows, columns=columns)

# ─────────────────────────────────────────
# DATA FUNCTIONS
# ─────────────────────────────────────────
def get_users():
    return run_query("SELECT user_id, zip_code FROM POWERPILOT.MAIN.users")

def get_devices(user_id):
    df = run_query(
        "SELECT device_name, power_on_watts, power_idle_watts, hours_on_per_day, hours_idle_per_day FROM POWERPILOT.MAIN.devices WHERE user_id = ?",
        params=[user_id]
    )
    devices = []
    for _, row in df.iterrows():
        def safe(val, default=0):
            try:
                f = float(val)
                return f if f == f else default  # NaN check
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

def get_rates(zip_code):
    df = run_query(
        "SELECT hour, cost_per_kwh FROM POWERPILOT.MAIN.energy_rates WHERE zip_code = ? ORDER BY hour",
        params=[zip_code]
    )
    # Build a lookup from whatever hours we have
    rate_lookup = {}
    for _, row in df.iterrows():
        h = int(row["HOUR"])
        rate_lookup[h] = float(row["COST_PER_KWH"])

    # Fill all 24 hours by carrying forward the last known rate
    rates = []
    last_rate = 0.12
    for h in range(24):
        if h in rate_lookup:
            last_rate = rate_lookup[h]
        rates.append({"hour": h, "cost_per_kwh": last_rate})
    return rates

# ─────────────────────────────────────────
# OPTIMIZER (copied from optimizer.py)
# ─────────────────────────────────────────
def compute_energy_results(data):
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
    phantom_pct = round(phantom_kwh / total_kwh * 100) if total_kwh and total_kwh == total_kwh else 0

    worst_set = set(worst_hours)
    total_on_hours = sum(d.get("hours_on_per_day", 0) for d in devices)
    peak_ratio = len(worst_set) / 24
    peak_usage_penalty = round(min(30, peak_ratio * total_on_hours * 5))
    inefficiency_penalty = round(min(30, phantom_pct * 0.6))
    off_peak_bonus = round(min(20, savings_pct * 0.2))
    power_score = max(0, min(100, 100 - peak_usage_penalty - inefficiency_penalty + off_peak_bonus))

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
    }

# ─────────────────────────────────────────
# AI ENGINE (Groq via raw requests — no groq package needed)
# ─────────────────────────────────────────
def call_groq(prompt, max_tokens=1024):
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def generate_recommendation(data):
    devices = data.get("devices", [])
    rates = data.get("energy_rates", [])
    results = data.get("computed_results", {})
    power_score = results.get("power_score", 50)

    prompt = f"""You are an energy optimization AI assistant. Analyze this user's energy usage data and return actionable recommendations.

User devices and usage:
{json.dumps(devices, indent=2)}

Time-of-use energy rates (cost per kWh by hour):
{json.dumps(rates, indent=2)}

Computed energy summary:
{json.dumps(results, indent=2)}

The user's current PowerScore is {power_score}/100.
Estimate new_energy_score as what their score could reach if they follow your recommendations (must be higher than {power_score}).

Return a JSON object with exactly this structure (no extra text, just JSON):
{{
  "current_energy_score": {power_score},
  "new_energy_score": <integer higher than {power_score}, max 100>,
  "recommendations": ["<tip>", "<tip>", "<tip>"],
  "estimated_monthly_savings": <float dollars>,
  "insights": ["<insight>", "<insight>"],
  "best_usage_hours": [<hour integers>],
  "worst_usage_hours": [<hour integers>]
}}"""

    raw = call_groq(prompt, max_tokens=1024)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception:
        return {"error": "Failed to parse AI response", "raw": raw}

def ask_question(question, data):
    devices = data.get("devices", [])
    results = data.get("computed_results", {})
    rates = data.get("energy_rates", [])

    prompt = f"""You are PowerPilot, a friendly home energy advisor. The user is looking at their home energy dashboard and has a question.

Their devices:
{json.dumps(devices, indent=2)}

Their energy rates by hour:
{json.dumps(rates, indent=2)}

Their current usage summary:
{json.dumps(results, indent=2)}

The user asks: "{question}"

Answer in 2-4 sentences. Be specific to their actual devices and data. Be friendly and practical. No jargon."""

    return call_groq(prompt, max_tokens=512)

# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "ai_result" not in st.session_state:
    st.session_state.ai_result = None
if "data" not in st.session_state:
    st.session_state.data = None
if "computed" not in st.session_state:
    st.session_state.computed = None

# ─────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────
st.markdown("""
<div class="pilot-header">
    <div class="pilot-logo">⚡</div>
    <div>
        <div class="pilot-title">PowerPilot</div>
        <div class="pilot-sub">SMART ENERGY ADVISOR</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# USER SELECTOR
# ─────────────────────────────────────────
users_df = get_users()
user_ids = users_df["USER_ID"].tolist()
selected_user = st.selectbox("Select User", user_ids, label_visibility="collapsed")

zip_row = users_df[users_df["USER_ID"] == selected_user].iloc[0]
zip_code = zip_row["ZIP_CODE"]

devices = get_devices(selected_user)
rates = get_rates(zip_code)

data = {
    "user_id": selected_user,
    "devices": devices,
    "energy_rates": rates,
}
computed = compute_energy_results(data)
data["computed_results"] = computed
st.session_state.data = data
st.session_state.computed = computed

# ─────────────────────────────────────────
# POWERSCORE + TOP METRICS
# ─────────────────────────────────────────
power_score = computed["power_score"]
total_kwh = computed["summary"]["total_kwh_per_day"]
total_cost = computed["summary"]["total_cost_per_month"]
potential_savings = computed["optimization"]["potential_monthly_savings_dollars"]
phantom_pct = computed["phantom_load"]["percentage_of_total"]

col1, col2, col3, col4 = st.columns([1.2, 1, 1, 1])

with col1:
    st.markdown(f"""
    <div class="score-ring-wrap">
        <div class="score-number">{power_score}</div>
        <div class="score-label">PowerScore</div>
        <div class="score-bar-bg">
            <div class="score-bar-fill" style="width:{power_score}%"></div>
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
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value metric-accent-green">${potential_savings}<span class="metric-unit">/mo</span></div>
        <div class="metric-label">Potential Savings</div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
# TABS
# ─────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["⚡ Rates & Hours", "📊 Devices", "🤖 AI Advisor", "💬 Chat"])

# ── TAB 1: RATES & HOURS CHART ──
with tab1:
    st.markdown('<div class="section-header">Time-of-Use Rates <div class="section-line"></div></div>', unsafe_allow_html=True)

    best_hours = set(computed["optimization"]["best_hours"])
    worst_hours = set(computed["optimization"]["worst_hours"])

    rate_map = {r["hour"]: r["cost_per_kwh"] for r in rates}
    all_hours = list(range(24))
    max_rate = max(rate_map.values()) if rate_map else 0.25
    min_rate = min(rate_map.values()) if rate_map else 0.10

    cells = ""
    labels = ""
    for h in all_hours:
        rate = rate_map.get(h, rate_map.get(max(k for k in rate_map if k <= h), 0.13))
        height_pct = int(((rate - min_rate) / (max_rate - min_rate + 0.001)) * 80 + 20)

        if h in worst_hours:
            color = "#FF3366"
        elif h in best_hours:
            color = "#00FF94"
        else:
            color = "#1E3A5F"

        cells += f'<div class="hour-cell" style="background:{color};height:{height_pct}%;">&nbsp;</div>'
        labels += f'<div class="hour-label">{h:02d}</div>'

    st.markdown(f"""
    <div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;padding:1.5rem;">
        <div style="display:flex;justify-content:space-between;margin-bottom:0.5rem;">
            <span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;">HOUR OF DAY (0-23)</span>
            <span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;">
                <span style="color:#00FF94;">■</span> Cheapest &nbsp;
                <span style="color:#FF3366;">■</span> Most Expensive
            </span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(24,1fr);gap:3px;height:80px;align-items:end;">
            {cells}
        </div>
        <div style="display:grid;grid-template-columns:repeat(24,1fr);gap:3px;margin-top:4px;">
            {labels}
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        <div class="metric-card" style="margin-top:1rem;">
            <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Best Hours to Run Devices</div>
            <div style="font-family:Space Mono,monospace;font-size:1.2rem;color:#00FF94;margin-top:0.5rem;">
                {", ".join(f"{h:02d}:00" for h in sorted(best_hours))}
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        st.markdown(f"""
        <div class="metric-card" style="margin-top:1rem;">
            <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Avoid These Hours</div>
            <div style="font-family:Space Mono,monospace;font-size:1.2rem;color:#FF3366;margin-top:0.5rem;">
                {", ".join(f"{h:02d}:00" for h in sorted(worst_hours))}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Phantom load
    st.markdown('<div class="section-header" style="margin-top:2rem;">Hidden Energy Waste <div class="section-line"></div></div>', unsafe_allow_html=True)
    phantom_watts = computed["phantom_load"]["total_watts"]
    phantom_kwh = computed["phantom_load"]["daily_kwh"]

    st.markdown(f"""
    <div class="metric-card">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Phantom Load</div>
                <div style="font-family:Space Mono,monospace;font-size:1.5rem;color:#FF6B35;margin-top:0.3rem;">{phantom_pct}% of total usage</div>
                <div style="font-size:0.8rem;color:#4A6080;margin-top:0.3rem;">{phantom_watts}W idle draw · {phantom_kwh} kWh/day wasted</div>
            </div>
        </div>
        <div class="phantom-bar-bg">
            <div class="phantom-bar-fill" style="width:{min(phantom_pct,100)}%"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── TAB 2: DEVICE BREAKDOWN ──
with tab2:
    st.markdown('<div class="section-header">Device Breakdown <div class="section-line"></div></div>', unsafe_allow_html=True)

    breakdown = computed["breakdown"]

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

# ── TAB 3: AI ADVISOR ──
with tab3:
    st.markdown('<div class="section-header">AI Recommendations <div class="section-line"></div></div>', unsafe_allow_html=True)

    if st.button("⚡ Optimize My Usage"):
        with st.spinner("Analyzing your energy profile..."):
            result = generate_recommendation(st.session_state.data)
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

            st.markdown('<div style="margin-top:1.5rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Recommendations</div>', unsafe_allow_html=True)
            for rec in result.get("recommendations", []):
                st.markdown(f'<div class="rec-card">→ {rec}</div>', unsafe_allow_html=True)

            st.markdown('<div style="margin-top:1rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Insights</div>', unsafe_allow_html=True)
            for insight in result.get("insights", []):
                st.markdown(f'<div class="insight-card">◆ {insight}</div>', unsafe_allow_html=True)
        else:
            st.error("AI response error. Check your Groq API key in secrets.")

# ── TAB 4: CHAT ──
with tab4:
    st.markdown('<div class="section-header">Chat with PowerPilot <div class="section-line"></div></div>', unsafe_allow_html=True)

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">⚡ {msg["content"]}</div>', unsafe_allow_html=True)

    question = st.text_input("Ask anything about your energy usage...", key="chat_input")
    if st.button("Send") and question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.spinner("Thinking..."):
            answer = ask_question(question, st.session_state.data)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()
