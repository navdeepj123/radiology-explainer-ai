from services.ollama_service import generate_with_ollama
from services.groq_service import generate_with_groq

def generate_with_provider(prompt, provider="ollama"):
    try:
        if provider == "groq":
            return generate_with_groq(prompt)

        return generate_with_ollama(prompt)

    except Exception as e:
        print("Provider failed, using Ollama:", e)
        return generate_with_ollama(prompt)