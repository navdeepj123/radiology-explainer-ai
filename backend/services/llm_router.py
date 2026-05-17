from services.ollama_service import generate_with_ollama
from services.groq_service import generate_with_groq
from services.openai_service import generate_with_openai

def generate_with_provider(prompt, provider="ollama"):

    try:

        if provider == "groq":
            return generate_with_groq(prompt)

        elif provider == "openai":
            return generate_with_openai(prompt)

        return generate_with_ollama(prompt)

    except Exception as e:

        print("Provider failed, using Ollama:", e)

        return generate_with_ollama(prompt)