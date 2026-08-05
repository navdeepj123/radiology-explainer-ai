"""
ClearScan — Radiology Report Explainer
3-page Flask app: Home → Analyze → Results + Chatbot
"""

import os
import re
import io
import pdfplumber
from datetime import datetime
from flask import Flask, request, render_template, session, jsonify
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "static")
)

app.secret_key = os.environ.get("FLASK_SECRET", "clearscan-secret-key-2025")
CORS(app)

from services.rag_service import generate_explanation, get_length_instruction, get_detail_instruction
from services.llm_router import generate_with_provider


CRISIS_KEYWORDS = [
    "suicidal", "suicide", "kill myself", "end my life", "don't want to live",
    "no reason to live", "better off dead", "self harm", "cut myself",
    "want to die", "can't go on", "hopeless", "harm myself",
    "not worth living", "give up on life", "end it all", "hurt myself"
]

MAX_CHAT_TURNS = 6

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
    Turns session["chat_messages"] (list of {role, content}) into a
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

    session["report_text"]   = report_text
    session["provider"]      = provider
    session["ollama_model"]  = ollama_model
    session["language"]      = language
    session["answer_length"] = answer_length
    session["detail_level"]  = detail_level
    session["chat_messages"] = []  # new report → start a fresh chat conversation

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

    if isinstance(results, dict):
        session["detected_terms"] = results.get("detected_terms", [])

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


# ── ANALYZE AJAX (single-page UI, PDF + language + style support) ──────────────

@app.route("/analyze_ajax", methods=["POST"])
def analyze_ajax():
    """
    Same logic as /analyze POST but returns JSON.
    Called by the new Analyze.html via fetch() — no page reload needed.
    Results + chatbot all appear on the same page.
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

    session["report_text"]   = report_text
    session["provider"]      = provider
    session["ollama_model"]  = ollama_model
    session["language"]      = language
    session["answer_length"] = answer_length
    session["detail_level"]  = detail_level
    session["chat_messages"] = []  # new report → start a fresh chat conversation

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

    if isinstance(results, dict):
        session["detected_terms"] = results.get("detected_terms", [])

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
        "risk_level":  results.get("risk_level",  "unknown"),
        "risk_reason": results.get("risk_reason", ""),
        "summary":     results.get("summary",     ""),
        "findings":    results.get("findings",    []),
        "terms":       results.get("terms",       []),
    })


# ── CHAT ──────────────────────────────────────────────────────────────────────

@app.route("/chat", methods=["POST"])
def chat():

    data           = request.get_json(silent=True) or {}
    user_msg       = data.get("message", "").strip()
    language       = data.get("language", session.get("language", "English"))
    answer_length  = data.get("answer_length", session.get("answer_length", "standard"))
    detail_level   = data.get("detail_level", session.get("detail_level", "medium"))
    provider       = session.get("provider", "groq")
    ollama_model   = session.get("ollama_model", "llama3.2:1b")
    report         = session.get("report_text", "")
    detected_terms = session.get("detected_terms", [])
    chat_messages  = session.get("chat_messages", [])

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

    chat_messages.append({"role": "user", "content": user_msg})
    chat_messages.append({"role": "assistant", "content": reply})
    session["chat_messages"] = chat_messages[-(MAX_CHAT_TURNS * 2):]

    return jsonify({"reply": reply})


# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)