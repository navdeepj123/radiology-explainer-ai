"""
auth_service.py — Optional account system (like claude.ai: usable without
an account, but you need one for your history to be saved permanently).

Uses Flask-Login for session management and werkzeug's password hashing
(PBKDF2-SHA256) — passwords are NEVER stored in plain text, only their hash.
"""

import re
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class User(UserMixin):
    """Thin wrapper around a MongoDB user document, for Flask-Login."""

    def __init__(self, doc):
        self._doc = doc

    # Flask-Login requires get_id() to return a string
    def get_id(self):
        return str(self._doc["_id"])

    @property
    def owner_id(self):
        """The stable, permanent conversation-ownership key for this user —
        distinct from any anonymous cookie, and never changes."""
        return f"user:{self._doc['_id']}"

    @property
    def email(self):
        return self._doc.get("email", "")

    @property
    def name(self):
        return self._doc.get("name", "") or self.email.split("@")[0]


class AuthService:
    def __init__(self, users_col):
        self.users_col = users_col

    def _available(self):
        return self.users_col is not None

    # ---- validation -----------------------------------------------------

    def validate_registration(self, email, password, name):
        email = (email or "").strip().lower()
        password = password or ""
        name = (name or "").strip()

        if not email or not EMAIL_RE.match(email):
            return "Please enter a valid email address."
        if len(password) < 8:
            return "Password must be at least 8 characters."
        if not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
            return "Password must include at least one uppercase letter and one number."
        if not self._available():
            return "Account system is temporarily unavailable. Please try again shortly."
        if self.users_col.find_one({"email": email}):
            return "An account with this email already exists."
        return None  # no error

    # ---- register / login ------------------------------------------------

    def register(self, email, password, name):
        email = email.strip().lower()
        name = name.strip()
        doc = {
            "email": email,
            "name": name,
            "password_hash": generate_password_hash(password),
            "created_at": datetime.utcnow(),
        }
        result = self.users_col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return User(doc)

    def authenticate(self, email, password):
        """Returns a User on success, or None on invalid credentials.
        Deliberately returns the same generic failure for 'no such email'
        and 'wrong password' so a login form can't be used to discover
        which emails are registered."""
        if not self._available():
            return None
        email = (email or "").strip().lower()
        doc = self.users_col.find_one({"email": email})
        if not doc:
            return None
        if not check_password_hash(doc["password_hash"], password or ""):
            return None
        return User(doc)

    def get_by_id(self, user_id):
        if not self._available():
            return None
        try:
            from bson.objectid import ObjectId
            doc = self.users_col.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        return User(doc) if doc else None
