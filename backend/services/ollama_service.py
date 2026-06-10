import requests

def _call_ollama(prompt, model, timeout=180):
    system_instruction = """You are a professional radiology explanation assistant for patients.
Explain reports clearly, calmly, and accurately.
Do not diagnose. Do not say 'Dear patient'. Do not write email style.
Do not use greetings or signatures. Always structure the answer with headings.
IMPORTANT: If the prompt includes a list of detected terms, your explanation MUST be consistent with ALL of them.
Never say a finding is absent or normal if it appears in the detected terms list.
Do not contradict the detected terms under any circumstances.\n\n"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": system_instruction + prompt,
                "stream": False
            },
            timeout=timeout
        )
        if response.status_code != 200:
            raise Exception(f"Ollama HTTP error: {response.status_code}")
        data = response.json()
        if "response" not in data:
            raise Exception(f"Unexpected Ollama response: {data}")
        return data["response"]
    except requests.exceptions.ConnectionError:
        raise Exception("Ollama is not running. Start it with: ollama serve")
    except requests.exceptions.Timeout:
        raise Exception("Ollama timed out.")


def generate_with_ollama(prompt, model="llama3.2:1b"):
    return _call_ollama(prompt, model, timeout=180)