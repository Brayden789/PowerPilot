import json


def build_recommendation_prompt(data: dict) -> str:
    devices = data.get("devices", [])
    rates = data.get("energy_rates", [])
    results = data.get("computed_results", {})

    return f"""You are an energy optimization AI assistant. Analyze this user's energy usage data and return actionable recommendations.

User devices and usage:
{json.dumps(devices, indent=2)}

Time-of-use energy rates (cost per kWh by hour):
{json.dumps(rates, indent=2)}

Computed energy summary:
{json.dumps(results, indent=2)}

Return a JSON object with exactly this structure (no extra text, just JSON):
{{
  "current_energy_score": <integer 0-100, lower is worse>,
  "new_energy_score": <integer 0-100, projected after recommendations>,
  "recommendations": [
    "<specific actionable tip>",
    "<specific actionable tip>",
    "<specific actionable tip>"
  ],
  "estimated_monthly_savings": <float dollars>,
  "insights": [
    "<insight about usage pattern>",
    "<insight about usage pattern>"
  ],
  "best_usage_hours": [<list of hour integers, 0-23, when rates are cheapest>],
  "worst_usage_hours": [<list of hour integers, 0-23, when rates are most expensive>]
}}"""
