import os
import requests
from dotenv import load_dotenv

load_dotenv()

def generate_with_gemini(prompt):
    api_key = os.getenv("OPENROUTER_API_KEY")

    system_prompt = """
You are a professional radiology explanation assistant for patients.
Explain reports clearly, calmly, and accurately.
Do not diagnose.
Do not say 'Dear patient'.
Do not write email style.
Do not use greetings or signatures.
Always structure the answer with headings.
IMPORTANT: If the prompt includes a list of detected terms, your explanation MUST be consistent with ALL of them.
Never say a finding is absent or normal if it appears in the detected terms list.
Do not contradict the detected terms under any circumstances.
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "ClearScan Radiology Explainer"
    }

    body = {
        "model": "google/gemini-2.0-flash-lite-001",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 700,
        "temperature": 0.2
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=body
    )

    if response.status_code != 200:
        raise Exception(f"OpenRouter error {response.status_code}: {response.text}")

    return response.json()["choices"][0]["message"]["content"]