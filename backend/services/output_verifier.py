"""
output_verifier.py — Naya safety layer.

Purpose: AI (chahe explanation ho, translation ho, ya chatbot reply ho)
jo bhi text generate karta hai, usko confirmed dataset terms ke against
verify karta hai — taaki agar AI kisi confirmed RISK finding ko galti se
"normal"/"absent" keh de (hallucination/contradiction), to system usko
turant pakad le.

Ye tumhare retriever.py ke is_negated() logic ko hi reuse karta hai,
bas input report ke bajaye AI ke apne output text pe chalta hai.

IMPORTANT: kuch dataset terms khud "benign/nothing found" type hote hain
(jaise "unremarkable", "no acute findings") — inke naam me hi negation
words hote hain, isliye inhe contradiction-check se exclude karte hain.
"""

import re

NEGATION_WORDS = [
    "no ", "not ", "without ", "absent ",
    "negative for ", "no evidence of ",
    "no signs of ", "none ", "neither ",
    "not identified", "not seen",
    "not present", "not noted",
    "not detected", "not found",
    "normal", "unremarkable", "clear"
]

# Terms jinka poora matlab hi "kuch abnormal nahi mila" hai — inke output
# me negation words hona EXPECTED/CORRECT hai, hallucination nahi.
BENIGN_TERM_KEYWORDS = [
    "unremarkable", "no acute", "no abnormality",
    "normal study", "no significant", "no focal"
]


def _is_benign_term(term_lower):
    return any(kw in term_lower for kw in BENIGN_TERM_KEYWORDS)


def _segments(text):
    return re.split(r'[.!?\n]|(?:\s*\*\s*)', text)


def verify_output(ai_text, confirmed_terms):
    """
    ai_text: AI ne jo bhi text generate kiya (summary, translation, ya
             chatbot reply) — plain text ya HTML dono chalega
    confirmed_terms: retriever.py se aaye retrieved_terms list
                      (jinme har item me "term" key hai)

    Returns: {
        "passed": bool,              # True agar koi contradiction nahi mila
        "checked_count": int,        # kitne (non-benign) terms check kiye
        "failed_terms": [str, ...]   # jo terms contradict hue unke naam
    }
    """
    if not confirmed_terms or not ai_text:
        return {"passed": True, "checked_count": 0, "failed_terms": []}

    clean_text = re.sub(r'<[^>]+>', ' ', str(ai_text))  # HTML tags hata do
    text_lower = clean_text.lower()
    segments = [s.lower().strip() for s in _segments(text_lower) if s.strip()]

    failed_terms = []
    checked_count = 0

    for item in confirmed_terms:
        term = item.get("term", "").lower().strip()
        if not term:
            continue

        # benign "nothing found" type terms skip karo — inke liye negation
        # words hona hi sahi/expected hai
        if _is_benign_term(term):
            continue

        checked_count += 1
        term_mentioned = term in text_lower

        if not term_mentioned:
            failed_terms.append(item.get("term", ""))
            continue

        for seg in segments:
            if term in seg and any(neg in seg for neg in NEGATION_WORDS):
                failed_terms.append(item.get("term", ""))
                break

    return {
        "passed": len(failed_terms) == 0,
        "checked_count": checked_count,
        "failed_terms": list(set(failed_terms)),
    }