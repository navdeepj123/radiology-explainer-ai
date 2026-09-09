from services.ollama_service import generate_with_ollama
from services.groq_service import generate_with_groq
from services.gemini_service import generate_with_gemini
from services.openai_service import generate_with_openai
from services.mode_names import to_internal_provider, to_public_mode


def _is_valid_response(response):
    return response is not None and str(response).strip() != ""


def _build_prompt(prompt, detected_terms=None):
    if not detected_terms:
        return prompt

    terms_list = "\n".join([f"- {item['term']}" for item in detected_terms])

    return f"""The following medical terms were CONFIRMED detected in this radiology report:
{terms_list}

Your explanation MUST acknowledge ALL of these findings. Do NOT say any of them are absent or normal.

{prompt}"""


def generate_with_provider(prompt, provider="ollama", detected_terms=None, ollama_model="llama3.2:1b", allow_fallback=True):
    provider = to_internal_provider(provider)

    final_prompt = _build_prompt(prompt, detected_terms)

    try:
        if provider == "ollama":
            response = generate_with_ollama(final_prompt, model=ollama_model)

        elif provider == "groq":
            response = generate_with_groq(final_prompt)

        elif provider == "gemini":
            response = generate_with_gemini(final_prompt)

        elif provider == "openai":
            response = generate_with_openai(final_prompt)

        else:
            return "Unknown provider selected."

        if _is_valid_response(response):
            return response

        raise Exception(f"Empty response from {provider}")

    except Exception as e:
        print(f"⚠️ {provider} failed: {str(e)}")

        if provider == "ollama":
            return (
                "⚠️ On-device mode is not available right now.<br><br>"
                "This mode needs the local processing service running on your "
                "computer. Start it, keep it running, and try again — or switch "
                "to Fast, Balanced, or Enhanced mode from the menu instead."
            )

        if not allow_fallback:
            # Benchmarking/testing a specific provider in isolation - surface
            # the real failure instead of silently switching providers, so
            # results for this provider aren't mislabeled as another one's.
            return f"""
<div class="explain-output">
    <div class="risk-box">
        <h3>Service Temporarily Unavailable</h3>
        <p>{to_public_mode(provider)} mode failed and fallback was disabled: {str(e)}</p>
    </div>
</div>
"""

        fallback_order = ["groq", "gemini", "openai"]

        for fallback_provider in fallback_order:
            if fallback_provider == provider:
                continue

            try:
                print(f"🔄 Trying fallback provider: {fallback_provider}")

                if fallback_provider == "groq":
                    fallback_response = generate_with_groq(final_prompt)

                elif fallback_provider == "gemini":
                    fallback_response = generate_with_gemini(final_prompt)

                elif fallback_provider == "openai":
                    fallback_response = generate_with_openai(final_prompt)

                if _is_valid_response(fallback_response):
                    return fallback_response

            except Exception as fallback_error:
                print(f"⚠️ Fallback {fallback_provider} failed: {str(fallback_error)}")

        return """
<div class="explain-output">
    <div class="risk-box">
        <h3>Service Temporarily Unavailable</h3>
        <p>The selected processing mode is not responding right now. Please try again or choose another mode.</p>
    </div>
</div>
"""