"""
Single generic blueprint serving ALL health tools.
Also saves conversations (MongoDB / guest store) and provides a
tool-scoped follow-up chat endpoint.
"""

from flask import Blueprint, request, jsonify, g, current_app
from services.health_tools.tool_registry import get_tool_class, list_tools
from services.health_tools.tools_config import TOOLS_CONFIG
from services.llm_router import generate_with_provider
from services.rag_service import get_length_instruction, get_detail_instruction

health_tools_bp = Blueprint("health_tools", __name__, url_prefix="/api/health-tools")


@health_tools_bp.route("/list", methods=["GET"])
def get_tools_list():
    return jsonify({"tools": TOOLS_CONFIG})


@health_tools_bp.route("/<tool_id>/analyze", methods=["POST"])
def analyze(tool_id):
    tool_class = get_tool_class(tool_id)
    if tool_class is None:
        return jsonify({
            "success": False,
            "errors": [f"Unknown tool '{tool_id}'. Available: {list_tools()}"]
        }), 404

    payload = request.get_json(silent=True) or {}
    user_input = payload.get("input", {})
    provider = payload.get("provider", "groq")
    answer_length = payload.get("answer_length", "standard")
    detail_level = payload.get("detail_level", "medium")

    options = payload.get("options", {})
    options.setdefault("answer_length", answer_length)
    options.setdefault("detail_level", detail_level)

    tool_instance = tool_class(user_input=user_input, provider=provider, options=options)
    result = tool_instance.run()

    if result.get("success"):
        conv_store = current_app.config.get("CONV_STORE")
        if conv_store is not None:
            cfg = TOOLS_CONFIG.get(tool_id, {})
            preview_text = next(iter(user_input.values()), "") if user_input else ""

            answer_text = result.get("result")
            if isinstance(answer_text, dict):
                answer_text = answer_text.get("explanation") or str(answer_text)

            conv_id = conv_store.create(
                g.owner_id, str(preview_text), provider,
                options.get("ollama_model", "llama3.2:1b"),
                "English", answer_length, detail_level,
                {"summary": answer_text, "risk_level": "unknown"},
                kind="health_tool", tool_id=tool_id, tool_name=cfg.get("name", tool_id)
            )
            result["conversation_id"] = conv_id

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@health_tools_bp.route("/<tool_id>/chat", methods=["POST"])
def chat(tool_id):
    """Follow-up questions, restricted to this tool's topic only."""
    cfg = TOOLS_CONFIG.get(tool_id)
    if not cfg:
        return jsonify({"reply": "Unknown tool."}), 404

    payload = request.get_json(silent=True) or {}
    conv_id = payload.get("conversation_id")
    message = (payload.get("message") or "").strip()
    provider = payload.get("provider", "groq")
    answer_length = payload.get("answer_length", "standard")
    detail_level = payload.get("detail_level", "medium")
    ollama_model = payload.get("ollama_model", "llama3.2:1b")

    if not message:
        return jsonify({"reply": "Please type a message."})

    conv_store = current_app.config.get("CONV_STORE")
    doc = conv_store.get(conv_id, g.owner_id) if conv_id else None
    if not doc:
        return jsonify({"reply": "Please ask your first question above to start this chat."})

    chat_messages = doc.get("chat_messages", [])

    length_instruction = get_length_instruction(answer_length)
    detail_instruction = get_detail_instruction(detail_level)

    system = (
        f"You are the {cfg['name']} assistant for ClearScan.\n"
        f"{cfg['name']} — {cfg['description']}\n\n"
        f"The user's original input was: {doc.get('report_text', '')}\n"
        f"Your initial answer was: {doc.get('results', {}).get('summary', '')}\n\n"
        "RULES:\n"
        f"1. ONLY answer questions related to {cfg['name']} ({cfg['description']}).\n"
        f"2. If the question is unrelated, say: \"I can only help with questions about {cfg['name']}.\"\n"
        "3. Do not diagnose. Do not give specific medication dosing instructions.\n"
        "4. Keep answers simple and patient-friendly.\n"
        "5. Always suggest discussing medical decisions with a doctor.\n"
        f"6. {length_instruction}\n"
        f"7. {detail_instruction}\n"
    )

    history_lines = []
    for m in chat_messages[-12:]:
        speaker = "Patient" if m.get("role") == "user" else "Assistant"
        history_lines.append(f"{speaker}: {m.get('content', '')}")
    history_block = ("\n".join(history_lines) + "\n") if history_lines else ""

    full_prompt = system + "\n" + history_block + "\nPatient question: " + message

    try:
        reply = generate_with_provider(
            full_prompt, provider, detected_terms=[], ollama_model=ollama_model
        )
    except Exception as e:
        return jsonify({"reply": f"Something went wrong: {str(e)}"})

    chat_messages.append({"role": "user", "content": message})
    chat_messages.append({"role": "assistant", "content": reply})
    chat_messages = chat_messages[-12:]

    conv_store.update_chat(conv_id, g.owner_id, chat_messages, "English", answer_length, detail_level)

    return jsonify({"reply": reply})