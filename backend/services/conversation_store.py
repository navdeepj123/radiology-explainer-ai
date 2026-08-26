"""
conversation_store.py — Dual-backend conversation persistence.

Design
------
ClearScan supports optional login (like claude.ai): anyone can use the app
without an account, but conversation history is only PERMANENTLY saved if
they're logged in.

Rather than scattering "if logged in / else" branches across every route in
app.py, this module hides the two backends behind one small interface:

  - Authenticated owners  (owner_id = "user:<mongo _id>")
        -> persisted forever in MongoDB, same as before Flask-Login existed.

  - Guest owners          (owner_id = the anonymous cs_owner_id cookie value)
        -> held in an in-memory, per-process TTL store. Full functionality
           (multi-turn chat, multiple conversations, rename/delete) works
           exactly the same as a logged-in user during the browser session,
           but nothing touches the database and everything is purged after
           GUEST_TTL_SECONDS of inactivity or on server restart.

When a guest registers or logs in, app.py calls migrate_guest_to_user() to
move their in-memory conversations into MongoDB under their new account,
so they don't lose what they were just doing.

Note: the in-memory guest store is per-process. That's fine for a single
Flask dev server (this project's deployment target), but a multi-worker
production deployment would need a shared store (e.g. Redis with a TTL)
instead — noted here as a known scaling limitation, not fixed by this store.
"""

import threading
import time
import uuid
from datetime import datetime

GUEST_TTL_SECONDS = 60 * 60 * 6  # guest conversations expire after 6 hours idle
MAX_CONVERSATIONS = 5

_guest_lock = threading.Lock()
_guest_store = {}   # owner_id -> {conv_id: {..doc.., "_last_touched": epoch}}


def _purge_expired_guests():
    cutoff = time.time() - GUEST_TTL_SECONDS
    with _guest_lock:
        for owner_id in list(_guest_store.keys()):
            convs = _guest_store[owner_id]
            for conv_id in list(convs.keys()):
                if convs[conv_id]["_last_touched"] < cutoff:
                    del convs[conv_id]
            if not convs:
                del _guest_store[owner_id]


def _clean_history_text(text):
    return " ".join(str(text).split())[:80]


class ConversationStore:
    """Unified interface used by app.py — callers don't need to know or
    care whether a given owner_id is backed by Mongo or the guest store."""

    def __init__(self, conversations_col):
        self.conversations_col = conversations_col

    # ---- helpers -----------------------------------------------------

    @staticmethod
    def is_guest_owner(owner_id):
        return not (isinstance(owner_id, str) and owner_id.startswith("user:"))

    # ---- create --------------------------------------------------------

    def create(self, owner_id, report_text, provider, ollama_model, language,
               answer_length, detail_level, results):
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
                "highlighted_terms": results.get("highlighted_terms", []) if isinstance(results, dict) else [],
            },
            "chat_messages": [],
            "preview":       _clean_history_text(report_text[:80]),
            "risk_level":    results.get("risk_level", "unknown") if isinstance(results, dict) else "unknown",
            "date":          datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "timestamp":     datetime.utcnow(),
        }

        if self.is_guest_owner(owner_id):
            return self._guest_create(owner_id, doc)
        return self._mongo_create(owner_id, doc)

    def _mongo_create(self, owner_id, doc):
        if self.conversations_col is None:
            return None
        try:
            result = self.conversations_col.insert_one(doc)
            conv_id = str(result.inserted_id)
            owner_convs = list(
                self.conversations_col.find({"owner_id": owner_id}).sort("timestamp", -1)
            )
            if len(owner_convs) > MAX_CONVERSATIONS:
                for extra in owner_convs[MAX_CONVERSATIONS:]:
                    self.conversations_col.delete_one({"_id": extra["_id"]})
            return conv_id
        except Exception as e:
            print(f"⚠️ MongoDB unavailable, conversation not saved: {e}")
            return None

    def _guest_create(self, owner_id, doc):
        _purge_expired_guests()
        conv_id = uuid.uuid4().hex
        doc["_id"] = conv_id
        doc["_last_touched"] = time.time()
        with _guest_lock:
            convs = _guest_store.setdefault(owner_id, {})
            convs[conv_id] = doc
            if len(convs) > MAX_CONVERSATIONS:
                oldest = sorted(convs.values(), key=lambda d: d["timestamp"])[0]
                del convs[oldest["_id"]]
        return conv_id

    # ---- list ----------------------------------------------------------

    def list_for_owner(self, owner_id):
        if self.is_guest_owner(owner_id):
            _purge_expired_guests()
            with _guest_lock:
                convs = list(_guest_store.get(owner_id, {}).values())
            convs.sort(key=lambda d: d["timestamp"], reverse=True)
            return [
                {
                    "id": d["_id"], "preview": d["preview"], "title": d.get("custom_title"),
                    "provider": d["provider"], "risk_level": d["risk_level"], "date": d["date"],
                }
                for d in convs
            ]

        if self.conversations_col is None:
            return []
        try:
            docs = self.conversations_col.find({"owner_id": owner_id}).sort("timestamp", -1)
            return [
                {
                    "id": str(d["_id"]), "preview": d["preview"], "title": d.get("custom_title"),
                    "provider": d["provider"], "risk_level": d["risk_level"], "date": d["date"],
                }
                for d in docs
            ]
        except Exception as e:
            print(f"⚠️ MongoDB unavailable: {e}")
            return []

    # ---- full list for trend/analytics views ------------------------------

    def list_full_for_owner(self, owner_id):
        """
        /trends ke liye — sidebar wale list_for_owner() ke ulat, ye poore
        conversation docs deta hai (detected_terms, risk_level, date samet),
        oldest -> newest order me, taaki chart left-to-right padha jaye.
        Guest aur logged-in dono owners ke liye kaam karta hai.
        """
        if self.is_guest_owner(owner_id):
            _purge_expired_guests()
            with _guest_lock:
                convs = list(_guest_store.get(owner_id, {}).values())
            convs.sort(key=lambda d: d["timestamp"])
            return [dict(d) for d in convs]

        if self.conversations_col is None:
            return []
        try:
            docs = self.conversations_col.find({"owner_id": owner_id}).sort("timestamp", 1)
            return list(docs)
        except Exception as e:
            print(f"⚠️ MongoDB unavailable: {e}")
            return []

    # ---- get one ---------------------------------------------------------

    def get(self, conv_id, owner_id):
        if self.is_guest_owner(owner_id):
            with _guest_lock:
                doc = _guest_store.get(owner_id, {}).get(conv_id)
            return dict(doc) if doc else None

        if self.conversations_col is None:
            return None
        try:
            from bson.objectid import ObjectId
            doc = self.conversations_col.find_one({"_id": ObjectId(conv_id), "owner_id": owner_id})
        except Exception:
            doc = None
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    # ---- delete ---------------------------------------------------------

    def delete(self, conv_id, owner_id):
        if self.is_guest_owner(owner_id):
            with _guest_lock:
                convs = _guest_store.get(owner_id, {})
                if conv_id in convs:
                    del convs[conv_id]
                    return True
            return False

        if self.conversations_col is None:
            return None  # signals "db unavailable" to caller
        try:
            from bson.objectid import ObjectId
            result = self.conversations_col.delete_one({"_id": ObjectId(conv_id), "owner_id": owner_id})
        except Exception:
            return False
        return result.deleted_count > 0

    # ---- rename ---------------------------------------------------------

    def rename(self, conv_id, owner_id, title):
        if self.is_guest_owner(owner_id):
            with _guest_lock:
                convs = _guest_store.get(owner_id, {})
                if conv_id in convs:
                    convs[conv_id]["custom_title"] = title
                    return True
            return False

        if self.conversations_col is None:
            return None
        try:
            from bson.objectid import ObjectId
            result = self.conversations_col.update_one(
                {"_id": ObjectId(conv_id), "owner_id": owner_id},
                {"$set": {"custom_title": title}}
            )
        except Exception:
            return False
        return result.matched_count > 0

    # ---- update chat (after each /chat turn) ----------------------------

    def update_chat(self, conv_id, owner_id, chat_messages, language, answer_length, detail_level):
        if self.is_guest_owner(owner_id):
            with _guest_lock:
                convs = _guest_store.get(owner_id, {})
                if conv_id in convs:
                    convs[conv_id]["chat_messages"] = chat_messages
                    convs[conv_id]["language"] = language
                    convs[conv_id]["answer_length"] = answer_length
                    convs[conv_id]["detail_level"] = detail_level
                    convs[conv_id]["_last_touched"] = time.time()
            return

        if self.conversations_col is None:
            return
        try:
            from bson.objectid import ObjectId
            self.conversations_col.update_one(
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

    # ---- guest -> account migration (the "sign in mid-chat" feature) ----

    def migrate_guest_to_user(self, guest_owner_id, user_owner_id):
        """
        Moves every conversation a guest built up during this browser
        session into MongoDB under their new account, the moment they
        register or log in. Returns how many conversations were migrated.
        """
        if self.conversations_col is None:
            return 0

        with _guest_lock:
            guest_convs = list(_guest_store.pop(guest_owner_id, {}).values())

        if not guest_convs:
            return 0

        migrated = 0
        for doc in sorted(guest_convs, key=lambda d: d["timestamp"]):
            doc.pop("_id", None)
            doc.pop("_last_touched", None)
            doc["owner_id"] = user_owner_id
            try:
                self.conversations_col.insert_one(doc)
                migrated += 1
            except Exception as e:
                print(f"⚠️ Could not migrate a guest conversation: {e}")

        # re-apply the MAX_CONVERSATIONS cap now that migrated ones are in
        try:
            owner_convs = list(
                self.conversations_col.find({"owner_id": user_owner_id}).sort("timestamp", -1)
            )
            if len(owner_convs) > MAX_CONVERSATIONS:
                for extra in owner_convs[MAX_CONVERSATIONS:]:
                    self.conversations_col.delete_one({"_id": extra["_id"]})
        except Exception:
            pass

        return migrated