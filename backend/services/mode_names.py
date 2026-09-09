"""
mode_names.py — Boundary translation between the public, product-facing
processing-mode names and the internal provider identifiers.

Everything a user can observe (the UI, request payloads, API responses)
speaks only in neutral product terms:

    fast / balanced / enhanced / local     — processing mode
    quick / deep                           — on-device model tier

The provider adapter modules underneath keep their own vendor-specific
names, because those are dictated by the third-party APIs they call.
Nothing above this boundary needs to know or expose them.
"""

MODE_TO_PROVIDER = {
    "fast":     "groq",
    "balanced": "gemini",
    "enhanced": "openai",
    "local":    "ollama",
}

LOCAL_MODEL_MAP = {
    "quick": "llama3.2:1b",
    "deep":  "mistral",
}

PROVIDER_TO_MODE = {v: k for k, v in MODE_TO_PROVIDER.items()}
LOCAL_MODEL_TO_PUBLIC = {v: k for k, v in LOCAL_MODEL_MAP.items()}

# Modes that support the follow-up assistant (everything except on-device,
# which uses its own inline chat panel).
CLOUD_PROVIDERS = ("groq", "gemini", "openai")


def to_internal_provider(mode):
    """Public mode name -> internal provider id. Passes through values that
    are already internal, so conversations saved before the rename still load."""
    mode = (mode or "fast").strip().lower()
    return MODE_TO_PROVIDER.get(mode, mode)


def to_internal_local_model(name):
    name = (name or "quick").strip().lower()
    return LOCAL_MODEL_MAP.get(name, name)


def to_public_mode(provider):
    return PROVIDER_TO_MODE.get((provider or "").strip().lower(), provider)


def to_public_local_model(name):
    return LOCAL_MODEL_TO_PUBLIC.get((name or "").strip().lower(), name)
