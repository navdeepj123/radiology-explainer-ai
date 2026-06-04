"""
ClearScan — Radiology Report Explainer
3-page Flask app: Home → Analyze → Results + Chatbot
"""

import os
import re
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

from services.rag_service import generate_explanation
from services.llm_router import generate_with_provider


CRISIS_KEYWORDS = [
    "suicidal", "suicide", "kill myself", "end my life", "don't want to live",
    "no reason to live", "better off dead", "self harm", "cut myself",
    "want to die", "can't go on", "hopeless", "harm myself",
    "not worth living", "give up on life", "end it all", "hurt myself"
]

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

RULES:
1. ONLY answer questions about this specific radiology report.
2. If unrelated, say: "I can only help you understand this radiology report."
3. Do not diagnose.
4. Do not give treatment or medicine advice.
5. Use simple patient-friendly language.
6. Keep answers under 120 words.
7. Use short bullet points if helpful.
8. Do not use markdown headings.
9. Do not use # symbols.
10. Do not use ``` code blocks.
11. Always suggest discussing medical decisions with a doctor.
"""


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


def clean_history_text(text):
    text = str(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = " ".join(text.split())
    return text


# ── HOME ──────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("home.html")


# ── ANALYZE (original — renders results.html) ─────────────────────────────────

@app.route("/analyze", methods=["GET", "POST"])
def analyze():

    if request.method == "GET":
        return render_template("Analyze.html")

    report_text = request.form.get("report_text", "").strip()
    question    = request.form.get("question", "").strip()
    provider    = request.form.get("provider", "groq").strip()
    uploaded    = request.files.get("report_file")

    if uploaded and uploaded.filename:
        try:
            report_text = uploaded.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            pass

    if not report_text:
        return render_template(
            "Analyze.html",
            error="Please paste your report text or upload a file."
        )

    session["report_text"] = report_text
    session["provider"]    = provider

    try:
        results = generate_explanation(report_text, provider, question)
    except TypeError:
        results = generate_explanation(report_text, provider)

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


# ── ANALYZE AJAX (new — returns JSON for single-page UI) ──────────────────────

@app.route("/analyze_ajax", methods=["POST"])
def analyze_ajax():
    """
    Same logic as /analyze POST but returns JSON.
    Called by the new Analyze.html via fetch() — no page reload needed.
    Results + chatbot all appear on the same page.
    """

    report_text = request.form.get("report_text", "").strip()
    provider    = request.form.get("provider", "groq").strip()
    uploaded    = request.files.get("report_file")

    # File upload support
    if uploaded and uploaded.filename:
        try:
            report_text = uploaded.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            pass

    if not report_text:
        return jsonify({"error": "Please paste your report text or upload a file."}), 400

    # Store in session so /chat works immediately after
    session["report_text"] = report_text
    session["provider"]    = provider

    # Run the same AI analysis
    try:
        results = generate_explanation(report_text, provider, "")
    except TypeError:
        results = generate_explanation(report_text, provider)

    # Save to history (same as /analyze)
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

    # Return JSON to frontend
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

    data     = request.get_json(silent=True) or {}
    user_msg = data.get("message", "").strip()
    provider = session.get("provider", "groq")
    report   = session.get("report_text", "")

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

    system = CHATBOT_SYSTEM.format(report=report)

    try:
        reply = generate_with_provider(
            user_msg,
            provider,
            system_prompt=system
        )
    except TypeError:
        full_prompt = system + "\n\nPatient question: " + user_msg
        reply = generate_with_provider(full_prompt, provider)

    reply = clean_ai_reply(reply)

    return jsonify({"reply": reply})


# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)