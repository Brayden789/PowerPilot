import streamlit as st
import snowflake.connector
import json
import os
import requests
import pandas as pd

# =============================================================================
# OPTIMIZER (inlined from optimizer.py)
# =============================================================================
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
    name = device_name.lower()
    if any(k in name for k in COOLING_KEYWORDS):
        return "cooling"
    if any(k in name for k in HEATING_KEYWORDS):
        return "heating"
    return "standard"


def compute_energy_results(data: dict) -> dict:
    devices = data.get("devices", [])
    rates = data.get("energy_rates", [])

    if not devices:
        return _empty_results()

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
        "summary": {"total_kwh_per_day": round(total_kwh, 3), "total_cost_per_month": total_cost_per_month},
        "breakdown": breakdown,
        "optimization": {
            "best_hours": best_hours,
            "worst_hours": worst_hours,
            "potential_savings_percent": savings_pct,
            "potential_monthly_savings_dollars": potential_savings,
        },
        "phantom_load": {"total_watts": round(phantom_watts, 1), "daily_kwh": phantom_kwh, "percentage_of_total": phantom_pct},
        "power_score": power_score,
        "monthly_projection": monthly_projection,
    }


def _compute_monthly_projection(devices: list, avg_rate: float) -> dict:
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
    return max(0, min(100, 100 - peak_usage_penalty - inefficiency_penalty + off_peak_bonus))


def _empty_results() -> dict:
    return {
        "summary": {"total_kwh_per_day": 0.0, "total_cost_per_month": 0.0},
        "breakdown": [],
        "optimization": {"best_hours": [], "worst_hours": [], "potential_savings_percent": 0, "potential_monthly_savings_dollars": 0.0},
        "phantom_load": {"total_watts": 0.0, "daily_kwh": 0.0, "percentage_of_total": 0},
        "power_score": 50,
        "monthly_projection": {m: 0.0 for m in MONTH_NAMES},
    }


# =============================================================================
# RATES FETCHER (inlined from rates_fetcher.py)
# =============================================================================
OPENEI_URL = "https://api.openei.org/utility_rates"


def get_rates_by_zip(zip_code: str) -> list:
    openei_key = st.secrets.get("OPENEI_API_KEY") or os.environ.get("OPENEI_API_KEY")
    try:
        params = {
            "version": 8,
            "api_key": openei_key,
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
            return _default_rates()
        return _parse_tou_rates(items[0])
    except Exception:
        return _default_rates()


def _parse_tou_rates(rate: dict) -> list:
    energy_rate_structure = rate.get("energyratestructure", [])
    weekday_schedule = rate.get("energyweekdayschedule", [])
    if energy_rate_structure and weekday_schedule:
        hour_rates = {}
        hour_periods = weekday_schedule[0] if weekday_schedule else []
        for hour, period_idx in enumerate(hour_periods):
            try:
                tier = energy_rate_structure[period_idx][0]
                rate_val = tier.get("rate", 0) + tier.get("adj", 0)
                hour_rates[hour] = round(rate_val, 4)
            except (IndexError, KeyError, TypeError):
                hour_rates[hour] = 0.13
        return [{"hour": h, "cost_per_kwh": hour_rates.get(h, 0.13)} for h in range(24)]
    flat_rate = 0.13
    try:
        flat_rate = rate["energyratestructure"][0][0]["rate"]
    except (KeyError, IndexError, TypeError):
        pass
    return _flat_to_tou(flat_rate)


def _flat_to_tou(base_rate: float) -> list:
    multipliers = {
        range(0, 6): 0.80,
        range(6, 9): 1.10,
        range(9, 16): 1.20,
        range(16, 21): 1.50,
        range(21, 24): 0.90,
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


def _default_rates() -> list:
    base = 0.13
    return _flat_to_tou(base)


# =============================================================================
# AI ENGINE (inlined from ai_engine.py + prompt_templates.py)
# =============================================================================
def _build_recommendation_prompt(data: dict) -> str:
    devices = data.get("devices", [])
    rates = data.get("energy_rates", [])
    results = data.get("computed_results", {})
    power_score = results.get("power_score", 50)
    return f"""You are an energy optimization AI assistant. Analyze this user's energy usage data and return actionable recommendations.

User devices and usage:
{json.dumps(devices, indent=2)}

Time-of-use energy rates (cost per kWh by hour):
{json.dumps(rates, indent=2)}

Computed energy summary:
{json.dumps(results, indent=2)}

The user's current PowerScore is {power_score}/100 (deterministically calculated — use this exact value).
Estimate new_energy_score as what their score could reach if they follow your recommendations (must be higher than {power_score}).

Return a JSON object with exactly this structure (no extra text, just JSON):
{{
  "current_energy_score": {power_score},
  "new_energy_score": <integer higher than {power_score}, max 100>,
  "recommendations": ["<specific actionable tip>","<specific actionable tip>","<specific actionable tip>"],
  "estimated_monthly_savings": <float dollars>,
  "insights": ["<insight about usage pattern>","<insight about usage pattern>"],
  "best_usage_hours": [<list of hour integers, 0-23>],
  "worst_usage_hours": [<list of hour integers, 0-23>]
}}"""


def _build_chat_prompt(question: str, data: dict) -> str:
    return f"""You are PowerPilot, a friendly home energy advisor. The user is looking at their home energy dashboard and has a question.

Their devices:
{json.dumps(data.get("devices", []), indent=2)}

Their energy rates by hour:
{json.dumps(data.get("energy_rates", []), indent=2)}

Their current usage summary:
{json.dumps(data.get("computed_results", {}), indent=2)}

The user asks: "{question}"

Answer in 2-4 sentences. Be specific to their actual devices and data. Be friendly and practical. No jargon."""


def _call_groq(prompt: str, max_tokens: int = 1024) -> str:
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def generate_energy_recommendation(data: dict) -> dict:
    prompt = _build_recommendation_prompt(data)
    raw = _call_groq(prompt, max_tokens=1024)
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to parse AI response", "raw": raw}


def ask_energy_question(question: str, data: dict) -> str:
    prompt = _build_chat_prompt(question, data)
    return _call_groq(prompt, max_tokens=512).strip()


# =============================================================================
# DEVICE DEFAULTS LOOKUP
# =============================================================================
DEVICE_DEFAULTS = {
    "refrigerator": {"watts": 150, "hours_on": 24, "hours_idle": 0},
    "fridge": {"watts": 150, "hours_on": 24, "hours_idle": 0},
    "freezer": {"watts": 100, "hours_on": 24, "hours_idle": 0},
    "dishwasher": {"watts": 1800, "hours_on": 1.5, "hours_idle": 0},
    "washing machine": {"watts": 500, "hours_on": 1.5, "hours_idle": 0},
    "washer": {"watts": 500, "hours_on": 1.5, "hours_idle": 0},
    "dryer": {"watts": 5000, "hours_on": 1, "hours_idle": 0},
    "microwave": {"watts": 1100, "hours_on": 0.3, "hours_idle": 0},
    "oven": {"watts": 2400, "hours_on": 1, "hours_idle": 0},
    "stove": {"watts": 2000, "hours_on": 1, "hours_idle": 0},
    "range": {"watts": 2000, "hours_on": 1, "hours_idle": 0},
    "tv": {"watts": 100, "hours_on": 5, "hours_idle": 1},
    "television": {"watts": 100, "hours_on": 5, "hours_idle": 1},
    "desktop": {"watts": 200, "hours_on": 6, "hours_idle": 2},
    "laptop": {"watts": 50, "hours_on": 6, "hours_idle": 2},
    "monitor": {"watts": 30, "hours_on": 6, "hours_idle": 1},
    "gaming console": {"watts": 150, "hours_on": 3, "hours_idle": 1},
    "ps5": {"watts": 200, "hours_on": 3, "hours_idle": 1},
    "xbox": {"watts": 150, "hours_on": 3, "hours_idle": 1},
    "air conditioner": {"watts": 1500, "hours_on": 8, "hours_idle": 0},
    "ac": {"watts": 1500, "hours_on": 8, "hours_idle": 0},
    "window ac": {"watts": 1200, "hours_on": 8, "hours_idle": 0},
    "central air": {"watts": 3500, "hours_on": 8, "hours_idle": 0},
    "heater": {"watts": 1500, "hours_on": 6, "hours_idle": 0},
    "space heater": {"watts": 1500, "hours_on": 6, "hours_idle": 0},
    "furnace": {"watts": 600, "hours_on": 8, "hours_idle": 0},
    "heat pump": {"watts": 1000, "hours_on": 8, "hours_idle": 0},
    "ceiling fan": {"watts": 75, "hours_on": 8, "hours_idle": 0},
    "fan": {"watts": 50, "hours_on": 8, "hours_idle": 0},
    "led light": {"watts": 10, "hours_on": 5, "hours_idle": 0},
    "light": {"watts": 10, "hours_on": 5, "hours_idle": 0},
    "lamp": {"watts": 15, "hours_on": 4, "hours_idle": 0},
    "water heater": {"watts": 4000, "hours_on": 3, "hours_idle": 0},
    "coffee maker": {"watts": 900, "hours_on": 0.5, "hours_idle": 0},
    "toaster": {"watts": 900, "hours_on": 0.1, "hours_idle": 0},
    "toaster oven": {"watts": 1200, "hours_on": 0.5, "hours_idle": 0},
    "hair dryer": {"watts": 1800, "hours_on": 0.2, "hours_idle": 0},
    "router": {"watts": 10, "hours_on": 24, "hours_idle": 0},
    "phone charger": {"watts": 10, "hours_on": 3, "hours_idle": 0},
    "ev charger": {"watts": 7200, "hours_on": 4, "hours_idle": 0},
    "pool pump": {"watts": 1500, "hours_on": 6, "hours_idle": 0},
    "hot tub": {"watts": 1500, "hours_on": 4, "hours_idle": 4},
    "dehumidifier": {"watts": 500, "hours_on": 8, "hours_idle": 0},
    "humidifier": {"watts": 35, "hours_on": 8, "hours_idle": 0},
    "security camera": {"watts": 10, "hours_on": 24, "hours_idle": 0},
    "smart speaker": {"watts": 3, "hours_on": 24, "hours_idle": 0},
}


def get_device_defaults_ai(device_name: str) -> dict:
    key = device_name.strip().lower()
    if key in DEVICE_DEFAULTS:
        return DEVICE_DEFAULTS[key]
    for k, v in DEVICE_DEFAULTS.items():
        if k in key or key in k:
            return v
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"watts": 100, "hours_on": 2.0, "hours_idle": 0.0}
    prompt = f"""You are a home energy expert. For the household device "{device_name}", provide typical average values.
Return ONLY a JSON object with no extra text or markdown:
{{"watts": <typical average wattage as integer>, "hours_on": <typical hours used per day as float>, "hours_idle": <typical idle hours per day as float>}}"""
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "max_tokens": 80, "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if "```" in raw:
            raw = raw.split("```")[1].split("```")[0].replace("json", "").strip()
        result = json.loads(raw)
        return {"watts": int(result.get("watts", 100)), "hours_on": float(result.get("hours_on", 2.0)), "hours_idle": float(result.get("hours_idle", 0.0))}
    except Exception:
        return {"watts": 100, "hours_on": 2.0, "hours_idle": 0.0}


# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="PowerPilot",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# STYLES
# =============================================================================
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

.device-row { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr; padding: 0.8rem 1rem; border-bottom: 1px solid #1E2A3A; align-items: center; }
.device-row:last-child { border-bottom: none; }
.device-row-header { font-size: 0.7rem; color: #4A6080; text-transform: uppercase; letter-spacing: 0.1em; font-family: 'Space Mono', monospace; }
.device-name { font-weight: 600; color: #E8EDF5; }
.device-val { font-family: 'Space Mono', monospace; font-size: 0.85rem; color: #A0B4CC; }
.device-cost { font-family: 'Space Mono', monospace; font-size: 0.85rem; color: #00FF94; }
.badge { display: inline-block; font-size: 0.6rem; font-family: 'Space Mono', monospace; padding: 2px 7px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.08em; }
.badge-cooling { background: #0A2A3A; color: #00D4FF; border: 1px solid #00D4FF44; }
.badge-heating { background: #2A1A0A; color: #FF6B35; border: 1px solid #FF6B3544; }
.badge-standard { background: #1A2030; color: #4A6080; border: 1px solid #2A3A5044; }

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

# =============================================================================
# SNOWFLAKE
# =============================================================================
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
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    cursor.execute(query, params) if params else cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    return pd.DataFrame(rows, columns=columns)

def run_write(query, params=None):
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    cursor.execute(query, params) if params else cursor.execute(query)
    conn.commit()
    cursor.close()

# =============================================================================
# DB HELPERS
# =============================================================================
def get_users():
    return run_query("SELECT user_id, zip_code FROM POWERPILOT.MAIN.users")

def get_devices(user_id):
    df = run_query(
        "SELECT device_name, power_on_watts, power_idle_watts, hours_on_per_day, hours_idle_per_day FROM POWERPILOT.MAIN.devices WHERE user_id = %s",
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

def add_device_to_db(user_id, device_name, power_on_watts, hours_on, hours_idle):
    run_write(
        "INSERT INTO POWERPILOT.MAIN.devices (user_id, device_name, power_on_watts, hours_on_per_day, hours_idle_per_day) VALUES (%s, %s, %s, %s, %s)",
        params=(user_id, device_name, float(power_on_watts), float(hours_on), float(hours_idle))
    )

def delete_device_from_db(user_id, device_name):
    run_write(
        "DELETE FROM POWERPILOT.MAIN.devices WHERE user_id = %s AND device_name = %s",
        params=(user_id, device_name)
    )

def update_user_zip(user_id, zip_code):
    run_write(
        "UPDATE POWERPILOT.MAIN.users SET zip_code = %s WHERE user_id = %s",
        params=(zip_code, user_id)
    )

# =============================================================================
# CACHED RATE FETCH
# =============================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_rates_cached(zip_code: str):
    rates = get_rates_by_zip(zip_code)
    source = "live" if len(rates) == 24 else "fallback"
    return rates, source

# =============================================================================
# SESSION STATE
# =============================================================================
for key, val in {
    "chat_history": [],
    "ai_result": None,
    "refresh_devices": 0,
    "device_lookup_name": "",
    "device_defaults": {"watts": 100, "hours_on": 2.0, "hours_idle": 0.0},
    "active_zip": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# =============================================================================
# HEADER
# =============================================================================
st.markdown("""
<div class="pilot-header">
    <div class="pilot-logo">⚡</div>
    <div>
        <div class="pilot-title">PowerPilot</div>
        <div class="pilot-tagline">Most people think saving energy means using less. When you use it matters just as much.</div>
    </div>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# USER + ZIP SELECTOR
# =============================================================================
with st.spinner("Loading profile..."):
    users_df = get_users().head(1)

user_ids = users_df["USER_ID"].tolist()
user_labels = {uid: f"Home {i+1}" for i, uid in enumerate(user_ids)}

col_user, col_zip, col_zip_btn, col_spacer = st.columns([1, 1, 0.6, 1.4])
with col_user:
    selected_label = st.selectbox("Viewing profile for", options=list(user_labels.values()))
selected_user = [k for k, v in user_labels.items() if v == selected_label][0]

zip_row = users_df[users_df["USER_ID"] == selected_user].iloc[0]
if st.session_state.active_zip is None:
    st.session_state.active_zip = str(zip_row["ZIP_CODE"])

with col_zip:
    new_zip_input = st.text_input("ZIP Code", value=st.session_state.active_zip, max_chars=10)
with col_zip_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📍 Update ZIP"):
        new_zip = new_zip_input.strip()
        if new_zip and new_zip != st.session_state.active_zip:
            fetch_rates_cached.clear()
            st.session_state.active_zip = new_zip
            update_user_zip(selected_user, new_zip)
            st.success(f"ZIP updated to {new_zip}!")
            st.rerun()

with st.spinner("Fetching live energy rates..."):
    rates, rate_source = fetch_rates_cached(st.session_state.active_zip)

source_class = "rate-source-live" if rate_source == "live" else "rate-source-fallback"
source_label = "Live OpenEI Rates" if rate_source == "live" else "Estimated Rates"
st.markdown(f'<div style="margin-bottom:0.5rem;"><span class="rate-source-badge {source_class}">{source_label} — ZIP {st.session_state.active_zip}</span></div>', unsafe_allow_html=True)

with st.spinner("Fetching devices..."):
    _ = st.session_state.refresh_devices
    devices = get_devices(selected_user)

data = {"user_id": selected_user, "devices": devices, "energy_rates": rates}
computed = compute_energy_results(data)
data["computed_results"] = computed

# =============================================================================
# TOP METRICS
# =============================================================================
power_score = computed["power_score"]
total_kwh = computed["summary"]["total_kwh_per_day"]
total_cost = computed["summary"]["total_cost_per_month"]
potential_savings = computed["optimization"]["potential_monthly_savings_dollars"]
phantom_pct = computed["phantom_load"]["percentage_of_total"]
annual_cost = round(total_cost * 12, 2)

col1, col2, col3, col4, col5 = st.columns([1.2, 1, 1, 1, 1])
with col1:
    st.markdown(f'<div class="score-ring-wrap"><div class="score-number">{power_score}</div><div class="score-label">PowerScore</div><div class="score-bar-bg"><div class="score-bar-fill" style="--target-width:{power_score}%;width:{power_score}%"></div></div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-value metric-accent">{total_kwh}<span class="metric-unit"> kWh</span></div><div class="metric-label">Daily Usage</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="metric-value">${total_cost}<span class="metric-unit">/mo</span></div><div class="metric-label">Est. Monthly Cost</div><div class="metric-sub">${annual_cost}/yr</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><div class="metric-value metric-accent-green">${potential_savings}<span class="metric-unit">/mo</span></div><div class="metric-label">Potential Savings</div><div class="metric-sub">${round(potential_savings*12,2)}/yr</div></div>', unsafe_allow_html=True)
with col5:
    st.markdown(f'<div class="metric-card"><div class="metric-value metric-accent-orange">{phantom_pct}<span class="metric-unit">%</span></div><div class="metric-label">Phantom Load</div><div class="metric-sub">idle device waste</div></div>', unsafe_allow_html=True)

# =============================================================================
# TABS
# =============================================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["⚡ Rates & Hours", "📊 Devices", "📈 Projection", "🤖 AI Advisor", "💬 Chat"])

# ── TAB 1 ──
with tab1:
    st.markdown('<div class="section-header">Time-of-Use Rates <div class="section-line"></div></div>', unsafe_allow_html=True)
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
        bars_html += f'<div class="hour-bar-wrap"><div class="hour-tooltip">{h:02d}:00 — ${rate:.4f}/kWh</div><div class="hour-bar" style="background:{color};height:{height_pct}%;"></div></div>'
    bars_html += "</div>"
    labels_html = '<div style="display:grid;grid-template-columns:repeat(24,1fr);gap:3px;margin-top:4px;">' + "".join(f'<div class="hour-label">{h:02d}</div>' for h in range(24)) + "</div>"

    st.markdown(f"""
    <div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;padding:1.5rem;">
        <div style="display:flex;justify-content:space-between;margin-bottom:0.8rem;">
            <span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;">HOUR OF DAY — hover for rate</span>
            <span style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;"><span style="color:#00FF94;">■</span> Cheapest &nbsp;<span style="color:#FF3366;">■</span> Most Expensive &nbsp;<span style="color:#1E3A5F;">■</span> Mid</span>
        </div>
        {bars_html}{labels_html}
    </div>""", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f'<div class="metric-card" style="margin-top:1rem;"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Best Hours to Run Devices</div><div style="font-family:Space Mono,monospace;font-size:1.1rem;color:#00FF94;margin-top:0.5rem;">{", ".join(f"{h:02d}:00" for h in sorted(best_hours)) if best_hours else "N/A"}</div></div>', unsafe_allow_html=True)
    with col_b:
        st.markdown(f'<div class="metric-card" style="margin-top:1rem;"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Avoid These Hours</div><div style="font-family:Space Mono,monospace;font-size:1.1rem;color:#FF3366;margin-top:0.5rem;">{", ".join(f"{h:02d}:00" for h in sorted(worst_hours)) if worst_hours else "N/A"}</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top:2rem;">Hidden Energy Waste <div class="section-line"></div></div>', unsafe_allow_html=True)
    phantom_watts = computed["phantom_load"]["total_watts"]
    phantom_kwh = computed["phantom_load"]["daily_kwh"]
    st.markdown(f'<div class="metric-card"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Phantom Load</div><div style="font-family:Space Mono,monospace;font-size:1.5rem;color:#FF6B35;margin-top:0.3rem;">{phantom_pct}% of total usage</div><div style="font-size:0.8rem;color:#4A6080;margin-top:0.3rem;">{phantom_watts}W idle draw · {phantom_kwh} kWh/day wasted</div><div class="phantom-bar-bg"><div class="phantom-bar-fill" style="width:{min(phantom_pct,100)}%"></div></div></div>', unsafe_allow_html=True)

# ── TAB 2 ──
with tab2:
    st.markdown('<div class="section-header">Device Breakdown <div class="section-line"></div></div>', unsafe_allow_html=True)
    breakdown = computed["breakdown"]

    if not breakdown:
        st.markdown('<div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;padding:2rem;text-align:center;color:#4A6080;font-family:Space Mono,monospace;font-size:0.85rem;">No devices added yet. Add your first device below to start tracking usage.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;overflow:hidden;"><div class="device-row device-row-header"><div>Device</div><div>Type</div><div>kWh/day</div><div>Cost/month</div><div>Share</div></div>', unsafe_allow_html=True)
        for item in breakdown:
            share = round(item["kwh_per_day"] / total_kwh * 100) if total_kwh > 0 else 0
            dtype = item.get("device_type", "standard")
            badge_label = {"cooling": "❄ Cooling", "heating": "🔥 Heating", "standard": "⚙ Standard"}.get(dtype, "⚙ Standard")
            st.markdown(f'<div class="device-row"><div class="device-name">{item["device_name"]}</div><div><span class="badge badge-{dtype}">{badge_label}</span></div><div class="device-val">{item["kwh_per_day"]}</div><div class="device-cost">${item["cost_per_month"]}</div><div class="device-val">{share}%</div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.72rem;color:#4A6080;font-family:Space Mono,monospace;margin-top:0.6rem;padding:0.6rem 0.8rem;background:#0A1018;border-radius:8px;border:1px solid #1E2A3A;">❄ Cooling devices only counted Jun–Sep in projection. 🔥 Heating devices only counted Nov–Mar.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-header" style="margin-top:2rem;">Add a Device <div class="section-line"></div></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.75rem;color:#4A6080;font-family:Space Mono,monospace;margin-bottom:0.8rem;">⚡ Type a device name and click <strong style="color:#00D4FF;">Look Up Defaults</strong> to auto-fill wattage and hours.</div>', unsafe_allow_html=True)

    lc, bc = st.columns([3, 1])
    with lc:
        lookup_name = st.text_input("Device Name", placeholder="e.g. Refrigerator, Air Conditioner...", key="lookup_input")
    with bc:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔍 Look Up Defaults") and lookup_name:
            with st.spinner(f"Looking up '{lookup_name}'..."):
                st.session_state.device_defaults = get_device_defaults_ai(lookup_name)
                st.session_state.device_lookup_name = lookup_name

    defaults = st.session_state.device_defaults
    with st.form("add_device_form", clear_on_submit=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            new_name = st.text_input("Confirm Name", value=st.session_state.device_lookup_name)
        with fc2:
            new_watts = st.number_input("Power (watts)", min_value=1, max_value=20000, value=int(defaults["watts"]))
        with fc3:
            new_hours_on = st.number_input("Hours ON/day", min_value=0.0, max_value=24.0, value=float(defaults["hours_on"]), step=0.5)
        with fc4:
            new_hours_idle = st.number_input("Hours Idle/day", min_value=0.0, max_value=24.0, value=float(defaults["hours_idle"]), step=0.5)
        if st.form_submit_button("⚡ Add Device") and new_name:
            add_device_to_db(selected_user, new_name, new_watts, new_hours_on, new_hours_idle)
            st.session_state.refresh_devices += 1
            st.session_state.device_lookup_name = ""
            st.session_state.device_defaults = {"watts": 100, "hours_on": 2.0, "hours_idle": 0.0}
            st.success(f"Added {new_name}!")
            st.rerun()

    if breakdown:
        st.markdown('<div class="section-header" style="margin-top:1.5rem;">Remove a Device <div class="section-line"></div></div>', unsafe_allow_html=True)
        cd1, cd2 = st.columns([2, 1])
        with cd1:
            to_delete = st.selectbox("Select device to remove", [item["device_name"] for item in breakdown])
        with cd2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Remove"):
                delete_device_from_db(selected_user, to_delete)
                st.session_state.refresh_devices += 1
                st.success(f"Removed {to_delete}")
                st.rerun()

# ── TAB 3 ──
with tab3:
    st.markdown('<div class="section-header">12-Month Cost Projection <div class="section-line"></div></div>', unsafe_allow_html=True)
    projection = computed["monthly_projection"]
    cp1, cp2 = st.columns([2, 1])
    with cp1:
        months = list(projection.keys())
        values = list(projection.values())
        max_val = max(values) if values and max(values) > 0 else 1
        min_val = min(values) if values else 0
        SVG_W, SVG_H = 580, 260
        PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 45
        chart_w = SVG_W - PAD_L - PAD_R
        chart_h = SVG_H - PAD_T - PAD_B
        n = len(months)

        def xp(i): return PAD_L + (i / (n - 1)) * chart_w if n > 1 else PAD_L + chart_w / 2
        def yp(v):
            span = max_val - min_val
            return PAD_T + chart_h / 2 if span == 0 else PAD_T + chart_h - ((v - min_val) / span) * chart_h

        pts = " ".join(f"{xp(i):.1f},{yp(v):.1f}" for i, v in enumerate(values))
        area = f"M{xp(0):.1f},{yp(values[0]):.1f} " + " ".join(f"L{xp(i):.1f},{yp(v):.1f}" for i, v in enumerate(values)) + f" L{xp(n-1):.1f},{PAD_T+chart_h} L{xp(0):.1f},{PAD_T+chart_h} Z"
        grid = ""
        for gi in range(5):
            gv = min_val + (max_val - min_val) * gi / 4
            gy = yp(gv)
            grid += f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{PAD_L+chart_w}" y2="{gy:.1f}" stroke="#1E2A3A" stroke-width="1"/>'
            grid += f'<text x="{PAD_L-8}" y="{gy+4:.1f}" text-anchor="end" font-family="Space Mono,monospace" font-size="9" fill="#4A6080">${gv:.0f}</text>'

        SEASON_COLORS = {"Jan":"#FF6B35","Feb":"#FF6B35","Mar":"#FFB347","Apr":"#00FF94","May":"#00FF94","Jun":"#00D4FF","Jul":"#00D4FF","Aug":"#00D4FF","Sep":"#00FF94","Oct":"#FFB347","Nov":"#FF6B35","Dec":"#FF6B35"}
        xlabels = "".join(f'<text x="{xp(i):.1f}" y="{PAD_T+chart_h+18}" text-anchor="middle" font-family="Space Mono,monospace" font-size="9" fill="#4A6080">{m}</text>' for i, m in enumerate(months))
        dots = "".join(f'<circle cx="{xp(i):.1f}" cy="{yp(v):.1f}" r="4" fill="{SEASON_COLORS.get(m,"#00D4FF")}" stroke="#080C12" stroke-width="2"><title>{m}: ${v}</title></circle>' for i, (m, v) in enumerate(zip(months, values)))

        svg = f"""<svg viewBox="0 0 {SVG_W} {SVG_H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
            <defs>
                <linearGradient id="aG" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#0066FF" stop-opacity="0.30"/><stop offset="100%" stop-color="#0066FF" stop-opacity="0.02"/></linearGradient>
                <linearGradient id="lG" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#0066FF"/><stop offset="100%" stop-color="#00D4FF"/></linearGradient>
            </defs>
            {grid}<path d="{area}" fill="url(#aG)"/>
            <polyline points="{pts}" fill="none" stroke="url(#lG)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
            {dots}{xlabels}
        </svg>"""

        st.markdown(f"""
        <div style="background:#0D1520;border:1px solid #1E2A3A;border-radius:16px;padding:1.5rem;">
            <div style="font-size:0.7rem;color:#4A6080;font-family:Space Mono,monospace;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem;">Seasonal cost projection — HVAC only counted in active months</div>
            {svg}
            <div style="display:flex;gap:16px;margin-top:0.6rem;font-family:Space Mono,monospace;font-size:0.65rem;color:#4A6080;">
                <span><span style="color:#FF6B35;">●</span> Winter (Heat)</span>
                <span><span style="color:#00D4FF;">●</span> Summer (AC)</span>
                <span><span style="color:#00FF94;">●</span> Spring/Fall</span>
                <span><span style="color:#FFB347;">●</span> Shoulder</span>
            </div>
        </div>""", unsafe_allow_html=True)

    with cp2:
        annual_total = round(sum(values), 2)
        annual_savings = round(annual_total * computed["optimization"]["potential_savings_percent"] / 100, 2)
        peak_month = max(projection, key=projection.get) if any(v > 0 for v in values) else "N/A"
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
        </div>""", unsafe_allow_html=True)

# ── TAB 4 ──
with tab4:
    st.markdown('<div class="section-header">AI Recommendations <div class="section-line"></div></div>', unsafe_allow_html=True)
    if not devices:
        st.markdown('<div class="rec-card" style="border-left-color:#FF6B35;">⚠️ Add at least one device in the <strong>Devices</strong> tab before running the AI optimizer.</div>', unsafe_allow_html=True)
    else:
        if st.button("⚡ Optimize My Usage"):
            with st.spinner("Analyzing your energy profile..."):
                st.session_state.ai_result = generate_energy_recommendation(data)

    if st.session_state.ai_result:
        result = st.session_state.ai_result
        if "error" not in result:
            new_score = result.get("new_energy_score", power_score)
            monthly_savings = result.get("estimated_monthly_savings", 0)
            cx, cy = st.columns(2)
            with cx:
                st.markdown(f'<div class="metric-card"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Score After Optimizing</div><div style="font-family:Space Mono,monospace;font-size:2rem;color:#00D4FF;margin-top:0.3rem;">{power_score} → {new_score}</div></div>', unsafe_allow_html=True)
            with cy:
                st.markdown(f'<div class="metric-card"><div style="font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;">Est. Monthly Savings</div><div style="font-family:Space Mono,monospace;font-size:2rem;color:#00FF94;margin-top:0.3rem;">${monthly_savings}</div></div>', unsafe_allow_html=True)
            st.markdown('<div style="margin-top:1.5rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Recommendations</div>', unsafe_allow_html=True)
            for rec in result.get("recommendations", []):
                st.markdown(f'<div class="rec-card">→ {rec}</div>', unsafe_allow_html=True)
            st.markdown('<div style="margin-top:1rem;font-size:0.7rem;color:#4A6080;text-transform:uppercase;letter-spacing:0.1em;font-family:Space Mono,monospace;margin-bottom:0.5rem;">Insights</div>', unsafe_allow_html=True)
            for insight in result.get("insights", []):
                st.markdown(f'<div class="insight-card">◆ {insight}</div>', unsafe_allow_html=True)
        else:
            st.error("AI response error. Check your Groq API key in secrets.")

# ── TAB 5 ──
with tab5:
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
            answer = ask_energy_question(question, data)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})
        st.rerun()
