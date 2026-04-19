# PowerPilot AI Engine

## Setup

```bash
cd ai
pip install -r requirements.txt
```

Add a `.env` file in the `ai/` folder:
```
GROQ_API_KEY=your_groq_key
OPENEI_API_KEY=your_openei_key
```

---

## How to call the AI engine (backend team)

### Step 1 — Fetch real energy rates by zip code
```python
from rates_fetcher import get_rates_by_zip

rates = get_rates_by_zip("13037")
```

### Step 2 — Build the data object with devices from Snowflake
```python
data = {
    "user_id": "u1",
    "devices": [
        {
            "device_name": "TV",
            "power_on_watts": 100,
            "hours_on_per_day": 3,
            "hours_idle_per_day": 21
        },
        {
            "device_name": "Xbox",
            "power_on_watts": 120,
            "hours_on_per_day": 2,
            "hours_idle_per_day": 22
        }
    ],
    "energy_rates": rates
}
```

### Step 3 — Run the optimizer (math, no API call)
```python
from optimizer import compute_energy_results

computed = compute_energy_results(data)
data["computed_results"] = computed
```

### Step 4 — Get AI recommendations
```python
from ai_engine import generate_energy_recommendation

result = generate_energy_recommendation(data)
```

**Returns:**
```json
{
  "current_energy_score": 86,
  "new_energy_score": 94,
  "recommendations": ["...", "...", "..."],
  "estimated_monthly_savings": 1.98,
  "insights": ["...", "..."],
  "best_usage_hours": [9, 10, 11, 12, 13, 14],
  "worst_usage_hours": [17, 18, 19]
}
```

### Step 5 — Chat feature (optional, for frontend Q&A)
```python
from ai_engine import ask_energy_question

answer = ask_energy_question("When should I run my dishwasher?", data)
# Returns a plain English string
```

---

## What the optimizer returns (computed_results)

```json
{
  "summary": {
    "total_kwh_per_day": 1.191,
    "total_cost_per_month": 5.34
  },
  "breakdown": [
    { "device_name": "TV", "kwh_per_day": 0.405, "cost_per_month": 1.82 }
  ],
  "optimization": {
    "best_hours": [9, 10, 11, 12, 13, 14],
    "worst_hours": [17, 18, 19],
    "potential_savings_percent": 37,
    "potential_monthly_savings_dollars": 1.98
  },
  "phantom_load": {
    "total_watts": 291.0,
    "daily_kwh": 0.291,
    "percentage_of_total": 24
  },
  "power_score": 86
}
```

---

## Snowflake table structure expected

**devices table**
| column | type |
|---|---|
| user_id | STRING |
| device_name | STRING |
| power_on_watts | FLOAT |
| hours_on_per_day | FLOAT |
| hours_idle_per_day | FLOAT |

**users table** (for zip code lookup)
| column | type |
|---|---|
| user_id | STRING |
| zip_code | STRING |
