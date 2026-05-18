from services.ollama_service import generate_with_ollama
from services.groq_service import generate_with_groq
from services.gemini_service import generate_with_gemini
from services.openai_service import generate_with_openai


def generate_with_provider(prompt, provider="ollama"):
    provider = provider.lower().strip()

    try:
        if provider == "groq":
            return generate_with_groq(prompt)

        elif provider == "gemini":
            return generate_with_gemini(prompt)

        elif provider == "openai":
            return generate_with_openai(prompt)

        elif provider == "ollama":
            return generate_with_ollama(prompt)

        else:
            return "Unknown provider selected."

    except Exception as e:
        if provider == "ollama":
            return (
                "⚠️ Ollama is not running on your computer.\n\n"
                "To use Ollama:\n"
                "1. Open a new PowerShell window\n"
                "2. Type: ollama serve\n"
                "3. Keep that window open and try again\n\n"
                "Or select Groq, Gemini, or OpenAI from the dropdown instead."
            )

        return f"⚠️ Error while using {provider}: {str(e)}"