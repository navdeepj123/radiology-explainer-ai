"""
ClearScan — Radiology Report Explainer
3-page Flask app: Home → Analyze → Results + Chatbot
"""

import os
import re
import io
import uuid
import time
import signal
import subprocess
import certifi
import pdfplumber
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify, g
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from services.output_verifier import verify_output

load_dotenv(override=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "static")
)

app.secret_key = os.environ.get("FLASK_SECRET", "clearscan-secret-key-2025")
CORS(app, supports_credentials=True)

# ── MONGODB CONNECTION (auto DNS-flush + retry + clean Ctrl+C) ─────────────

def _flush_dns():
    """Windows DNS cache clear karta hai — stale connection issues rokta hai."""
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=5)
    except Exception:
        pass  # agar Windows nahi hai ya command fail ho, chup-chaap ignore karo


def _connect_mongo_with_retry(uri, max_attempts=3):
    """
    MongoDB se connect karta hai, aur agar fail ho to DNS flush karke
    dubara try karta hai — bina user ko manually kuch karna pade.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            client = MongoClient(
                uri,
                tlsCAFile=certifi.where(),
                tlsAllowInvalidCertificates=True,   # TEMPORARY — diagnostic only, hata dena baad me
                serverSelectionTimeoutMS=8000,
                connectTimeoutMS=8000,
                socketTimeoutMS=8000,
                retryWrites=True,
            )
            client.admin.command("ping")  # turant test karo connection sahi hai ya nahi
            print(f"✅ MongoDB connected (attempt {attempt})")
            return client
        except Exception as e:
            print(f"⚠️ MongoDB connection attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                print("   Flushing DNS and retrying...")
                _flush_dns()
                time.sleep(2)
    print("❌ MongoDB could not connect after retries. App will run, but history/verification features will be unavailable until connection is restored.")
    return None


def _connect_mongo_safely(uri, max_attempts=3):
    """
    MongoDB se connect karta hai, DNS lookup ke waqt Ctrl+C ka
    messy traceback na aaye isliye SIGINT ko thodi der ke liye hold karta hai.
    """
    original_handler = signal.getsignal(signal.SIGINT)

    def _quiet_interrupt_handler(signum, frame):
        raise SystemExit(0)  # clean exit, koi traceback nahi

    try:
        signal.signal(signal.SIGINT, _quiet_interrupt_handler)
    except (ValueError, OSError):
        pass  # kuch environments me signal set nahi hota, ignore karo

    try:
        return _connect_mongo_with_retry(uri, max_attempts)
    finally:
        try:
            signal.signal(signal.SIGINT, original_handler)  # normal Ctrl+C wapas laga do
        except (ValueError, OSError):
            pass


MONGO_URI = os.environ.get("MONGO_URI")
mongo_client = _connect_mongo_safely(MONGO_URI)
db = mongo_client["clearscan"] if mongo_client is not None else None
conversations_col = db["conversations"] if db is not None else None
verification_logs_col = db["verification_logs"] if db is not None else None

OWNER_COOKIE_NAME = "cs_owner_id"
OWNER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year

from services.rag_service import generate_explanation, get_length_instruction, get_detail_instruction
from services.llm_router import generate_with_provider


CRISIS_KEYWORDS = [
    "suicidal", "suicide", "kill myself", "end my life", "don't want to live",
    "no reason to live", "better off dead", "self harm", "cut myself",
    "want to die", "can't go on", "hopeless", "harm myself",
    "not worth living", "give up on life", "end it all", "hurt myself"
]

MAX_CHAT_TURNS = 6
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


# ── OWNER COOKIE (before/after request) ─────────────────────────────────────

@app.before_request
def load_owner_id():
    owner_id = request.cookies.get(OWNER_COOKIE_NAME)
    if not owner_id:
        owner_id = uuid.uuid4().hex
        g.new_owner_id = owner_id   # after_request will set the cookie
    g.owner_id = owner_id


@app.after_request
def set_owner_cookie(response):
    new_owner_id = getattr(g, "new_owner_id", None)
    if new_owner_id:
        response.set_cookie(
            OWNER_COOKIE_NAME,
            new_owner_id,
            max_age=OWNER_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax"
        )
    return response


def get_language_instruction(language):
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


# ── VERIFICATION LOGGING ─────────────────────────────────────────────────

def log_verification(conv_id, provider, language, verification, source):
    """
    Har verification check ka result MongoDB me save karta hai.
    source: "explanation" (initial report explanation) ya "chat" (chatbot reply)
    Yehi tumhara research data hai — /verification-stats isi collection se
    accuracy numbers nikalta hai.
    """
    if verification_logs_col is None:
        return
    try:
        verification_logs_col.insert_one({
            "conv_id":       conv_id,
            "provider":      provider,
            "language":      language,
            "source":        source,
            "passed":        verification.get("passed", True),
            "checked_count": verification.get("checked_count", 0),
            "failed_terms":  verification.get("failed_terms", []),
            "timestamp":     datetime.utcnow(),
        })
    except Exception as e:
        print(f"⚠️ Verification logging failed: {e}")


# ── CONVERSATION HELPERS (MongoDB) ──────────────────────────────────────────

def create_conversation(owner_id, report_text, provider, ollama_model, language,
                         answer_length, detail_level, results):
    """
    Inserts a new conversation document into MongoDB, trims this owner's
    conversations to MAX_CONVERSATIONS (deletes oldest if over), and
    returns the new conversation's id as a string. Returns None if MongoDB
    is currently unavailable — the caller handles this gracefully.
    """
    if conversations_col is None:
        return None

    detected_terms = results.get("detected_terms", []) if isinstance(results, dict) else []

    doc = {
        "owner_id":       owner_id,
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
        "timestamp":     datetime.utcnow(),
    }

    try:
        result = conversations_col.insert_one(doc)
        conv_id = str(result.inserted_id)

        # keep only the most recent MAX_CONVERSATIONS for this owner
        owner_convs = list(
            conversations_col.find({"owner_id": owner_id}).sort("timestamp", -1)
        )
        if len(owner_convs) > MAX_CONVERSATIONS:
            for extra in owner_convs[MAX_CONVERSATIONS:]:
                conversations_col.delete_one({"_id": extra["_id"]})

        return conv_id
    except Exception as e:
        print(f"⚠️ MongoDB unavailable, conversation not saved: {e}")
        return None


def serialize_conv(doc):
    return {
        "id":             str(doc["_id"]),
        "report_text":    doc["report_text"],
        "provider":       doc["provider"],
        "ollama_model":   doc["ollama_model"],
        "language":       doc["language"],
        "answer_length":  doc.get("answer_length", "standard"),
        "detail_level":   doc.get("detail_level", "medium"),
        "detected_terms": doc.get("detected_terms", []),
        "results":        doc["results"],
        "chat_messages":  doc.get("chat_messages", []),
    }


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
        return render_template("Analyze.html", error="Please paste your report text or upload a file.")

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

    conv_id = create_conversation(g.owner_id, report_text, provider, ollama_model, language,
                                   answer_length, detail_level, results)

    # verify the explanation against confirmed terms and log it
    explanation_verification = results.get("verification") if isinstance(results, dict) else None
    if explanation_verification is None:
        explanation_verification = verify_output(
            results.get("summary", "") if isinstance(results, dict) else str(results),
            results.get("detected_terms", []) if isinstance(results, dict) else []
        )
    log_verification(conv_id, provider, language, explanation_verification, source="explanation")

    show_chatbot = provider in ("groq", "gemini", "openai")

    return render_template(
        "results.html",
        results=results,
        provider=provider,
        show_chatbot=show_chatbot,
        question=question,
    )


# ── ANALYZE AJAX (single-page UI, PDF + language + MongoDB conversations) ──────

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
    conv_id = create_conversation(g.owner_id, report_text, provider, ollama_model, language,
                                   answer_length, detail_level, results)

    # verify the explanation against confirmed terms and log it
    explanation_verification = results.get("verification") if isinstance(results, dict) else None
    if explanation_verification is None:
        explanation_verification = verify_output(
            results.get("summary", "") if isinstance(results, dict) else str(results),
            results.get("detected_terms", []) if isinstance(results, dict) else []
        )
    log_verification(conv_id, provider, language, explanation_verification, source="explanation")

    return jsonify({
        "conversation_id": conv_id,   # ← frontend saves this and sends it back on /chat; may be None if DB is down
        "risk_level":  results.get("risk_level",  "unknown"),
        "risk_reason": results.get("risk_reason", ""),
        "summary":     results.get("summary",     ""),
        "findings":    results.get("findings",    []),
        "terms":       results.get("terms",       []),
        "verification": explanation_verification,
    })


# ── CONVERSATIONS: list for sidebar ────────────────────────────────────────

@app.route("/conversations", methods=["GET"])
def list_conversations():
    if conversations_col is None:
        return jsonify({"conversations": [], "warning": "History temporarily unavailable"})
    try:
        docs = conversations_col.find({"owner_id": g.owner_id}).sort("timestamp", -1)
        items = [
            {
                "id":         str(d["_id"]),
                "preview":    d["preview"],
                "title":      d.get("custom_title"),   # NEW — renamed title, if set
                "provider":   d["provider"],
                "risk_level": d["risk_level"],
                "date":       d["date"],
            }
            for d in docs
        ]
        return jsonify({"conversations": items})
    except Exception as e:
        print(f"⚠️ MongoDB unavailable: {e}")
        return jsonify({"conversations": [], "warning": "History temporarily unavailable"})


# ── CONVERSATIONS: reload one full conversation (report + chat) ───────────

@app.route("/conversation/<conv_id>", methods=["GET"])
def get_conversation(conv_id):
    if conversations_col is None:
        return jsonify({"error": "Database temporarily unavailable"}), 503
    try:
        doc = conversations_col.find_one({"_id": ObjectId(conv_id), "owner_id": g.owner_id})
    except Exception:
        doc = None

    if not doc:
        return jsonify({"error": "Conversation not found"}), 404

    return jsonify(serialize_conv(doc))


# ── CONVERSATIONS: delete (NEW) ─────────────────────────────────────────

@app.route("/conversation/<conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    if conversations_col is None:
        return jsonify({"error": "Database temporarily unavailable"}), 503
    try:
        result = conversations_col.delete_one({"_id": ObjectId(conv_id), "owner_id": g.owner_id})
    except Exception:
        return jsonify({"error": "Invalid id"}), 400
    if result.deleted_count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"deleted": True})


# ── CONVERSATIONS: rename (NEW) ─────────────────────────────────────────

@app.route("/conversation/<conv_id>/rename", methods=["POST"])
def rename_conversation(conv_id):
    if conversations_col is None:
        return jsonify({"error": "Database temporarily unavailable"}), 503
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()[:100]
    if not title:
        return jsonify({"error": "Title required"}), 400
    try:
        result = conversations_col.update_one(
            {"_id": ObjectId(conv_id), "owner_id": g.owner_id},
            {"$set": {"custom_title": title}}
        )
    except Exception:
        return jsonify({"error": "Invalid id"}), 400
    if result.matched_count == 0:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"title": title})


# ── CHAT — reads/writes the given conversation's own chat thread ──────────

@app.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json(silent=True) or {}
    user_msg = data.get("message", "").strip()
    conv_id  = data.get("conversation_id")

    if not conv_id or conversations_col is None:
        return jsonify({"reply": "I don't have your report loaded. Please go back and submit your report first."})

    try:
        doc = conversations_col.find_one({"_id": ObjectId(conv_id), "owner_id": g.owner_id})
    except Exception:
        doc = None

    if not doc:
        return jsonify({"reply": "I don't have your report loaded. Please go back and submit your report first."})

    language       = data.get("language", doc.get("language", "English"))
    answer_length  = data.get("answer_length", doc.get("answer_length", "standard"))
    detail_level   = data.get("detail_level", doc.get("detail_level", "medium"))
    provider       = doc.get("provider", "groq")
    ollama_model   = doc.get("ollama_model", "llama3.2:1b")
    report         = doc.get("report_text", "")
    detected_terms = doc.get("detected_terms", [])
    chat_messages  = doc.get("chat_messages", [])

    if not user_msg:
        return jsonify({"reply": "Please type a message."})

    lower = user_msg.lower()

    if any(keyword in lower for keyword in CRISIS_KEYWORDS):
        return jsonify({"reply": CRISIS_REPLY, "is_crisis": True})

    if any(keyword in lower for keyword in OFF_TOPIC_KEYWORDS):
        return jsonify({
            "reply": (
                "I can only help you understand your radiology report. "
                "Please ask questions related to your report findings, "
                "medical terms, or summary. 😊"
            )
        })

    if not report:
        return jsonify({"reply": "I don't have your report loaded. Please go back and submit your report first."})

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

    full_prompt = system + "\n\n" + conversation_context + "\nPatient question: " + user_msg
    reply = generate_with_provider(full_prompt, provider, detected_terms=detected_terms, ollama_model=ollama_model)
    reply = clean_ai_reply(reply)

    # verify chatbot reply against confirmed terms and log it
    verification = verify_output(reply, detected_terms)
    log_verification(conv_id, provider, language, verification, source="chat")

    chat_messages.append({"role": "user", "content": user_msg})
    chat_messages.append({"role": "assistant", "content": reply})
    chat_messages = chat_messages[-(MAX_CHAT_TURNS * 2):]

    try:
        conversations_col.update_one(
            {"_id": ObjectId(conv_id)},
            {"$set": {
                "chat_messages": chat_messages,
                "language": language,
                "answer_length": answer_length,
                "detail_level": detail_level
            }}
        )
    except Exception as e:
        print(f"⚠️ Could not save chat turn to MongoDB: {e}")

    return jsonify({
        "reply": reply,
        "verification": verification
    })


# ── VERIFICATION STATS — research/accuracy dashboard data ────────────

@app.route("/verification-stats", methods=["GET"])
def verification_stats():
    if verification_logs_col is None:
        return jsonify({"stats": [], "warning": "Database temporarily unavailable"})
    pipeline = [
        {"$group": {
            "_id": {"provider": "$provider", "source": "$source"},
            "total": {"$sum": 1},
            "passed": {"$sum": {"$cond": ["$passed", 1, 0]}},
        }}
    ]
    results = list(verification_logs_col.aggregate(pipeline))
    stats = []
    for r in results:
        total = r["total"]
        passed = r["passed"]
        stats.append({
            "provider": r["_id"]["provider"],
            "source": r["_id"]["source"],
            "total_checks": total,
            "passed": passed,
            "accuracy_percent": round((passed / total) * 100, 1) if total else 0,
        })
    return jsonify({"stats": stats})


# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)