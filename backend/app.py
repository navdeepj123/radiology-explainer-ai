"""
ClearScan — Radiology Report Explainer
3-page Flask app: Home → Analyze → Results + Chatbot
Multi-conversation support: every "Analyse New Report" creates its own
conversation (report + chat thread) that can be reopened from the sidebar.
"""

import os
import re
import io
import uuid
import pdfplumber
from datetime import datetime
from flask import Flask, request, render_template, session, jsonify
from flask_cors import CORS
from flask_session import Session

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "static")
)

app.secret_key = os.environ.get("FLASK_SECRET", "clearscan-secret-key-2025")
CORS(app)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(BASE_DIR, "backend", "flask_session_data")
app.config["SESSION_PERMANENT"] = False
Session(app)

from services.rag_service import generate_explanation, get_length_instruction, get_detail_instruction
from services.llm_router import generate_with_provider


CRISIS_KEYWORDS = [
    "suicidal", "suicide", "kill myself", "end my life", "don't want to live",
    "no reason to live", "better off dead", "self harm", "cut myself",
    "want to die", "can't go on", "hopeless", "harm myself",
    "not worth living", "give up on life", "end it all", "hurt myself"
]

# Max number of Q&A exchanges to keep per conversation's chat history
MAX_CHAT_TURNS = 6

# Max number of conversations kept in the session (matches the sidebar limit)
MAX_CONVERSATIONS = 5

OFF_TOPIC_KEYWORDS = [
    "recipe", "movie", "weather", "sports", "politics", "code", "programming",
    "football", "cricket", "stock", "investment", "travel", "food", "game",
    "music", "song", "film", "celebrity", "news", "shopping"
]

CRISIS_REPLY = (
    "I'm really concerned about what you've shared — you are not alone, "
    "and support is available right now. 💙\n\n"
    "🇳🇿 New Zealand Support Services:\n\n"
    "🆘 Need urgent help?\n"
    "Call 111 immediately if you or someone else is in immediate danger.\n\n"
    "📞 Need to talk to someone now?\n"
    "Call or text 1737 anytime (24/7) to speak with a trained counsellor for free.\n\n"
    "💬 Lifeline Aotearoa:\n"
    "0800 543 354  (or text HELP to 4357)\n\n"
    "🧠 Suicide Crisis Helpline:\n"
    "0508 828 865  (0508 TAUTOKO)\n\n"
    "Please reach out to someone you trust or a healthcare professional today. "
    "Your wellbeing matters more than this report. 💙"
)

CHATBOT_SYSTEM = """
You are ClearScan Assistant — a warm AI that helps patients understand their radiology report.

The patient's radiology report is:
---
{report}
---

{detected_terms_section}

RULES:
1. ONLY answer questions about this specific radiology report.
2. If unrelated, say: "I can only help you understand this radiology report."
3. Do not diagnose.
4. Do not give treatment or medicine advice.
5. Use simple patient-friendly language.
6. Use short bullet points if helpful.
7. Do not use markdown headings.
8. Do not use # symbols.
9. Do not use ``` code blocks.
10. Always suggest discussing medical decisions with a doctor.
11. IMPORTANT: The detected terms listed above are CONFIRMED findings — never say they are absent or normal.
12. {language_instruction}
13. {length_instruction}
14. {detail_instruction}
"""


def get_language_instruction(language):
    """
    Language ke hisaab se AI ko instruction deta hai.
    Hinglish ek special casual style hai, baaki normal languages hain.
    """
    if not language or language.lower() == "english":
        return "Respond in English."

    if language.lower() == "hinglish":
        return (
            "Respond in Hinglish — a casual mix of Hindi and English, "
            "the way young Indians speak. Example style: 'Aapka heart normal se "
            "thoda bada hai, but tension lene ki zaroorat nahi hai.' Keep it "
            "friendly and easy to understand."
        )

    return f"Respond ONLY in {language} language. Translate all medical explanations into {language}."


def clean_ai_reply(reply):
    if reply is None:
        return "Sorry, I could not get a response. Please try again."

    reply = str(reply).strip()
    reply = reply.replace("```html", "")
    reply = reply.replace("```HTML", "")
    reply = reply.replace("```Html", "")
    reply = reply.replace("```", "")
    reply = reply.replace("# ", "")
    reply = reply.replace("## ", "")
    reply = reply.strip()

    return reply


def build_conversation_context(chat_messages):
    """
    Turns a conversation's chat_messages (list of {role, content}) into a
    plain-text transcript the LLM can use as conversation memory.
    """
    if not chat_messages:
        return ""

    lines = []
    for msg in chat_messages:
        speaker = "Patient" if msg.get("role") == "user" else "Assistant"
        lines.append(f"{speaker}: {msg.get('content', '')}")

    return (
        "Previous conversation in this session (for context only, "
        "do not repeat it back):\n"
        + "\n".join(lines)
        + "\n"
    )


def clean_history_text(text):
    text = str(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = " ".join(text.split())
    return text


def extract_pdf_text(file_storage):
    """
    PDF file se text nikalta hai.
    file_storage = Flask ka request.files['report_file'] object
    Returns: (extracted_text, error_message)
    """
    try:
        file_bytes = file_storage.read()
        text_parts = []

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        full_text = "\n".join(text_parts).strip()

        if not full_text:
            return None, (
                "Could not find any readable text in this PDF. "
                "It might be a scanned image — please paste the text manually."
            )

        return full_text, None

    except Exception:
        return None, (
            "Could not read this PDF file. "
            "Please try again or paste the text manually."
        )


# ── CONVERSATION HELPERS ────────────────────────────────────────────────────

def create_conversation(report_text, provider, ollama_model, language,
                         answer_length, detail_level, results):
    """
    Builds a new conversation dict, stores it in session["conversations"],
    marks it active, trims the list to MAX_CONVERSATIONS, and returns its id.
    """
    conversations = session.get("conversations", {})

    conv_id = uuid.uuid4().hex[:12]
    detected_terms = results.get("detected_terms", []) if isinstance(results, dict) else []

    conversations[conv_id] = {
        "id":             conv_id,
        "report_text":    report_text,
        "provider":       provider,
        "ollama_model":   ollama_model,
        "language":       language,
        "answer_length":  answer_length,
        "detail_level":   detail_level,
        "detected_terms": detected_terms,
        "results": {
            "risk_level":  results.get("risk_level",  "unknown") if isinstance(results, dict) else "unknown",
            "risk_reason": results.get("risk_reason", "")        if isinstance(results, dict) else "",
            "summary":     results.get("summary",     "")        if isinstance(results, dict) else str(results),
            "findings":    results.get("findings",    [])        if isinstance(results, dict) else [],
            "terms":       results.get("terms",       [])        if isinstance(results, dict) else [],
        },
        "chat_messages": [],
        "preview":       clean_history_text(report_text[:80]),
        "risk_level":    results.get("risk_level", "unknown") if isinstance(results, dict) else "unknown",
        "date":          datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "timestamp":     datetime.now().isoformat(),
    }

    # keep only the most recent MAX_CONVERSATIONS conversations (oldest dropped)
    if len(conversations) > MAX_CONVERSATIONS:
        oldest_id = min(conversations, key=lambda k: conversations[k]["timestamp"])
        conversations.pop(oldest_id, None)

    session["conversations"] = conversations
    session["active_conversation_id"] = conv_id
    session.modified = True

    return conv_id


# ── HOME ──────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("home.html")


# ── ANALYZE (original — renders results.html) ─────────────────────────────────

@app.route("/analyze", methods=["GET", "POST"])
def analyze():

    if request.method == "GET":
        return render_template("Analyze.html")

    report_text   = request.form.get("report_text", "").strip()
    question      = request.form.get("question", "").strip()
    provider      = request.form.get("provider", "groq").strip()
    ollama_model  = request.form.get("ollama_model", "llama3.2:1b").strip()
    language      = request.form.get("language", "English").strip()
    answer_length = request.form.get("answer_length", "standard").strip()
    detail_level  = request.form.get("detail_level", "medium").strip()
    uploaded      = request.files.get("report_file")

    # File upload support (PDF + plain text fallback)
    if uploaded and uploaded.filename:
        filename_lower = uploaded.filename.lower()

        if filename_lower.endswith(".pdf"):
            extracted_text, pdf_error = extract_pdf_text(uploaded)
            if pdf_error:
                return render_template("Analyze.html", error=pdf_error)
            report_text = extracted_text
        else:
            try:
                report_text = uploaded.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                pass

    if not report_text:
        return render_template(
            "Analyze.html",
            error="Please paste your report text or upload a file."
        )

    try:
        results = generate_explanation(
            report_text, provider, question,
            ollama_model=ollama_model, language=language,
            answer_length=answer_length, detail_level=detail_level
        )
    except TypeError:
        try:
            results = generate_explanation(report_text, provider, question, ollama_model=ollama_model)
        except TypeError:
            results = generate_explanation(report_text, provider)

    # Create a conversation (report + its own chat thread) instead of
    # overwriting one global session state
    create_conversation(report_text, provider, ollama_model, language,
                         answer_length, detail_level, results)

    history      = session.get("history", [])
    summary_text = results.get("summary", "") if isinstance(results, dict) else str(results)
    summary_text = clean_history_text(summary_text)

    history.append({
        "date":     datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "provider": provider,
        "report":   clean_history_text(report_text[:150]),
        "summary":  summary_text[:250]
    })
    session["history"] = history[-5:]

    show_chatbot = provider in ("groq", "gemini", "openai")

    return render_template(
        "results.html",
        results=results,
        provider=provider,
        show_chatbot=show_chatbot,
        question=question,
        history=session.get("history", [])
    )


# ── ANALYZE AJAX (single-page UI, PDF + language + multi-conversation) ─────────

@app.route("/analyze_ajax", methods=["POST"])
def analyze_ajax():
    """
    Same logic as /analyze POST but returns JSON.
    Called by Analyze.html via fetch() — no page reload needed.
    Every call here creates a NEW conversation (fresh report + its own chat
    thread), instead of overwriting the previous one.
    """

    report_text   = request.form.get("report_text", "").strip()
    provider      = request.form.get("provider", "groq").strip()
    ollama_model  = request.form.get("ollama_model", "llama3.2:1b").strip()
    language      = request.form.get("language", "English").strip()
    answer_length = request.form.get("answer_length", "standard").strip()
    detail_level  = request.form.get("detail_level", "medium").strip()
    uploaded      = request.files.get("report_file")

    # File upload support (PDF + plain text fallback)
    if uploaded and uploaded.filename:
        filename_lower = uploaded.filename.lower()

        if filename_lower.endswith(".pdf"):
            extracted_text, pdf_error = extract_pdf_text(uploaded)
            if pdf_error:
                return jsonify({"error": pdf_error}), 400
            report_text = extracted_text
        else:
            try:
                report_text = uploaded.read().decode("utf-8", errors="ignore").strip()
            except Exception:
                pass

    if not report_text:
        return jsonify({"error": "Please paste your report text or upload a file."}), 400

    try:
        results = generate_explanation(
            report_text, provider, "",
            ollama_model=ollama_model, language=language,
            answer_length=answer_length, detail_level=detail_level
        )
    except TypeError:
        try:
            results = generate_explanation(report_text, provider, "", ollama_model=ollama_model)
        except TypeError:
            results = generate_explanation(report_text, provider)

    # Create a fresh conversation (report + its own chat thread)
    conv_id = create_conversation(report_text, provider, ollama_model, language,
                                   answer_length, detail_level, results)

    history      = session.get("history", [])
    summary_text = results.get("summary", "") if isinstance(results, dict) else str(results)
    summary_text = clean_history_text(summary_text)

    history.append({
        "date":     datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "provider": provider,
        "report":   clean_history_text(report_text[:150]),
        "summary":  summary_text[:250]
    })
    session["history"] = history[-5:]

    return jsonify({
        "conversation_id": conv_id,   # ← frontend saves this and sends it back on /chat
        "risk_level":  results.get("risk_level",  "unknown"),
        "risk_reason": results.get("risk_reason", ""),
        "summary":     results.get("summary",     ""),
        "findings":    results.get("findings",    []),
        "terms":       results.get("terms",       []),
    })


# ── CONVERSATIONS: list for sidebar ────────────────────────────────────────

@app.route("/conversations", methods=["GET"])
def list_conversations():
    """
    Returns a lightweight list of this session's conversations
    (newest first) for rendering the 'Recent Reports' sidebar.
    """
    conversations = session.get("conversations", {})
    items = [
        {
            "id":         c["id"],
            "preview":    c["preview"],
            "provider":   c["provider"],
            "risk_level": c["risk_level"],
            "date":       c["date"],
        }
        for c in conversations.values()
    ]
    items.sort(key=lambda x: x["date"], reverse=True)
    return jsonify({
        "conversations": items,
        "active_conversation_id": session.get("active_conversation_id")
    })


# ── CONVERSATIONS: reload one full conversation (report + chat) ───────────

@app.route("/conversation/<conv_id>", methods=["GET"])
def get_conversation(conv_id):
    conversations = session.get("conversations", {})
    conv = conversations.get(conv_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404

    session["active_conversation_id"] = conv_id
    session.modified = True

    return jsonify({
        "id":             conv["id"],
        "report_text":    conv["report_text"],
        "provider":       conv["provider"],
        "ollama_model":   conv["ollama_model"],
        "language":       conv["language"],
        "answer_length":  conv.get("answer_length", "standard"),
        "detail_level":   conv.get("detail_level", "medium"),
        "results":        conv["results"],
        "chat_messages":  conv["chat_messages"],
    })


# ── CHAT — reads/writes the ACTIVE conversation's own chat thread ─────────

@app.route("/chat", methods=["POST"])
def chat():

    data     = request.get_json(silent=True) or {}
    user_msg = data.get("message", "").strip()

    conv_id = data.get("conversation_id") or session.get("active_conversation_id")
    conversations = session.get("conversations", {})
    conv = conversations.get(conv_id)

    if not conv:
        return jsonify({
            "reply": "I don't have your report loaded. Please go back and submit your report first."
        })

    language       = data.get("language", conv.get("language", "English"))
    answer_length  = data.get("answer_length", conv.get("answer_length", "standard"))
    detail_level   = data.get("detail_level", conv.get("detail_level", "medium"))
    provider       = conv.get("provider", "groq")
    ollama_model   = conv.get("ollama_model", "llama3.2:1b")
    report         = conv.get("report_text", "")
    detected_terms = conv.get("detected_terms", [])
    chat_messages  = conv.get("chat_messages", [])

    if not user_msg:
        return jsonify({"reply": "Please type a message."})

    lower = user_msg.lower()

    if any(keyword in lower for keyword in CRISIS_KEYWORDS):
        return jsonify({
            "reply":     CRISIS_REPLY,
            "is_crisis": True
        })

    if any(keyword in lower for keyword in OFF_TOPIC_KEYWORDS):
        return jsonify({
            "reply": (
                "I can only help you understand your radiology report. "
                "Please ask questions related to your report findings, "
                "medical terms, or summary. 😊"
            )
        })

    if not report:
        return jsonify({
            "reply": (
                "I don't have your report loaded. "
                "Please go back and submit your report first."
            )
        })

    if detected_terms:
        terms_list = "\n".join([f"- {item['term']}" for item in detected_terms])
        detected_terms_section = (
            f"Confirmed detected findings in this report:\n{terms_list}\n"
            "Never say any of the above findings are absent or normal."
        )
    else:
        detected_terms_section = ""

    language_instruction = get_language_instruction(language)
    length_instruction    = get_length_instruction(answer_length)
    detail_instruction    = get_detail_instruction(detail_level)

    system = CHATBOT_SYSTEM.format(
        report=report,
        detected_terms_section=detected_terms_section,
        language_instruction=language_instruction,
        length_instruction=length_instruction,
        detail_instruction=detail_instruction
    )

    conversation_context = build_conversation_context(chat_messages)

    full_prompt = (
        system
        + "\n\n"
        + conversation_context
        + "\nPatient question: "
        + user_msg
    )
    reply = generate_with_provider(full_prompt, provider, detected_terms=detected_terms, ollama_model=ollama_model)

    reply = clean_ai_reply(reply)

    # Store this exchange in THIS conversation's own chat thread (not a
    # single global one) so future questions have the right context and
    # switching conversations doesn't mix up chat histories.
    chat_messages.append({"role": "user", "content": user_msg})
    chat_messages.append({"role": "assistant", "content": reply})
    conv["chat_messages"]  = chat_messages[-(MAX_CHAT_TURNS * 2):]
    conv["language"]       = language        # remember latest choices for this conversation
    conv["answer_length"]  = answer_length
    conv["detail_level"]   = detail_level

    conversations[conv_id] = conv
    session["conversations"] = conversations
    session.modified = True

    return jsonify({"reply": reply})


# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)