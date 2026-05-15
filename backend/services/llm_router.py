from services.ollama_service import generate_with_ollama
from services.groq_service import generate_with_groq
from services.gemini_service import generate_with_gemini

def generate_with_provider(prompt, provider="ollama"):

    if provider == "groq":
        return generate_with_groq(prompt)

    if provider == "gemini":
        return generate_with_gemini(prompt)

    if provider == "ollama":
        try:
            return generate_with_ollama(prompt)
        except Exception as e:
            return (
                "⚠️ Ollama is not running on your computer.\n\n"
                "To use Ollama:\n"
                "1. Open a new PowerShell window\n"
                "2. Type: ollama serve\n"
                "3. Keep that window open and try again\n\n"
                "Or select Groq or Gemini from the dropdown instead — "
                "those work without any local setup."
            )

    return "Unknown provider selected."