from services.ollama_service import generate_with_ollama
from services.groq_service import generate_with_groq
from services.gemini_service import generate_with_gemini
from services.openai_service import generate_with_openai


def _is_valid_response(response):
    return response is not None and str(response).strip() != ""


def generate_with_provider(prompt, provider="ollama"):
    provider = provider.lower().strip()

    try:
        if provider == "ollama":
            response = generate_with_ollama(prompt)

        elif provider == "groq":
            response = generate_with_groq(prompt)

        elif provider == "gemini":
            response = generate_with_gemini(prompt)

        elif provider == "openai":
            response = generate_with_openai(prompt)

        else:
            return "Unknown provider selected."

        if _is_valid_response(response):
            return response

        raise Exception(f"Empty response from {provider}")

    except Exception as e:
        print(f"⚠️ {provider} failed: {str(e)}")

        if provider == "ollama":
            return (
                "⚠️ Ollama is not running on your computer.<br><br>"
                "To use Ollama:<br>"
                "1. Open a new PowerShell window<br>"
                "2. Type: <strong>ollama serve</strong><br>"
                "3. Keep that window open and try again<br><br>"
                "Or select Groq, Gemini, or OpenAI from the dropdown instead."
            )

        fallback_order = ["groq", "gemini", "openai"]

        for fallback_provider in fallback_order:
            if fallback_provider == provider:
                continue

            try:
                print(f"🔄 Trying fallback provider: {fallback_provider}")

                if fallback_provider == "groq":
                    fallback_response = generate_with_groq(prompt)

                elif fallback_provider == "gemini":
                    fallback_response = generate_with_gemini(prompt)

                elif fallback_provider == "openai":
                    fallback_response = generate_with_openai(prompt)

                if _is_valid_response(fallback_response):
                    return fallback_response

            except Exception as fallback_error:
                print(f"⚠️ Fallback {fallback_provider} failed: {str(fallback_error)}")

        return """
<div class="ai-output">
    <div class="risk-box">
        <h3>AI Service Temporary Issue</h3>
        <p>The selected AI provider is not responding right now. Please try again or choose another model.</p>
    </div>
</div>
"""