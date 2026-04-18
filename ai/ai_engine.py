import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
from prompt_templates import build_recommendation_prompt

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def generate_energy_recommendation(data: dict) -> dict:
    """
    Takes user energy JSON and returns AI optimization suggestions via Groq (Llama 3).
    """
    prompt = build_recommendation_prompt(data)

    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.choices[0].message.content

    try:
        # Claude returns JSON inside a markdown block sometimes
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        return {"error": "Failed to parse AI response", "raw": raw}
