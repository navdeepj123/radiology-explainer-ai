import requests

def generate_with_ollama(prompt):

    system_instruction = """You are a professional radiology explanation assistant for patients.
Explain reports clearly, calmly, and accurately.
Do not diagnose. Do not say 'Dear patient'. Do not write email style.
Do not use greetings or signatures. Always structure the answer with headings.
IMPORTANT: If the prompt includes a list of detected terms, your explanation MUST be consistent with ALL of them.
Never say a finding is absent or normal if it appears in the detected terms list.
Do not contradict the detected terms under any circumstances.\n\n"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral",
            "prompt": system_instruction + prompt,
            "stream": False
        }
    )

    data = response.json()

    return data["response"]