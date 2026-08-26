"""
output_verifier.py — Naya safety layer.

Purpose: AI (chahe explanation ho, translation ho, ya chatbot reply ho)
jo bhi text generate karta hai, usko confirmed dataset terms ke against
verify karta hai — taaki agar AI kisi confirmed RISK finding ko galti se
"normal"/"absent" keh de (hallucination/contradiction), to system usko
turant pakad le.

Ye tumhare retriever.py ke is_negated() logic se INSPIRED hai, lekin
retriever.py original (terse, clinical) report text pe chalta hai jahan
1 sentence = 1 finding hota hai. Yahan hum AI ke apne PATIENT-FRIENDLY
explanation text pe check kar rahe hain, jo natural prose hai — isme
AI aksar term ke bilkul paas negation-JAISE words use karta hai bina
kisi contradiction ke:
  - "heart appears larger than NORMAL (cardiomegaly)"   -> comparison,
    contradiction nahi
  - "lung is NOT fully expanded (atelectasis)"           -> ye khud
    atelectasis ki DEFINITION hai, contradiction nahi

Isliye "term ke paas koi bhi negation word hai kya" (loose proximity)
approach yahan kaam nahi karta — bahut false positives deta hai.

v3 fix: ab hum sirf SPECIFIC grammatical negation templates match
karte hain jo explicitly bolte hain "ye finding absent/present nahi
hai" — jaise "no {term}", "{term} is not present/seen/identified",
"without {term}", "{term} was ruled out", etc. Loose "koi bhi negation
word paas mein" wala check hata diya gaya hai.

IMPORTANT: kuch dataset terms khud "benign/nothing found" type hote hain
(jaise "unremarkable", "no acute findings") — inke naam me hi negation
words hote hain, isliye inhe contradiction-check se exclude karte hain.
"""

import re

# Terms jinka poora matlab hi "kuch abnormal nahi mila" hai — inke output
# me negation words hona EXPECTED/CORRECT hai, hallucination nahi.
BENIGN_TERM_KEYWORDS = [
    "unremarkable", "no acute", "no abnormality",
    "normal study", "no significant", "no focal"
]

# "no X or Y" jaisi shared-negation cases handle karne ke liye, negation
# aur term ke beech thode filler words allow karte hain (jaise
# "no fracture or hemorrhage" -> hemorrhage bhi negated hai).
_GAP = r"(?:\s+\w+){0,3}\s+"

# Presence-words jo "is/was/are/were not X" pattern me use hote hain.
_PRESENCE_WORDS = r"(?:present|seen|identified|found|noted|detected|visible|evident)"

# Direct absence-words jo term ke turant baad aa sakte hain.
_ABSENCE_WORDS = (
    r"(?:absent|ruled out|excluded|not detected|not identified|"
    r"not seen|not present|not found|not noted|not visible)"
)


def _is_benign_term(term_lower):
    return any(kw in term_lower for kw in BENIGN_TERM_KEYWORDS)


def _term_in_segment(term, seg):
    return re.search(r"\b" + re.escape(term) + r"\b", seg) is not None


def _build_contradiction_regex(term):
    t = re.escape(term)
    patterns = [
        rf"\bno{_GAP}{t}\b",
        rf"\bnone{_GAP}{t}\b",
        rf"\bneither{_GAP}{t}\b",
        rf"\bwithout{_GAP}{t}\b",
        rf"\bnegative for{_GAP}{t}\b",
        rf"\bno evidence of{_GAP}{t}\b",
        rf"\bno signs? of{_GAP}{t}\b",
        rf"\b{t}\b(?:\s+\w+){{0,4}}\s+(?:is|was|are|were)\s+not\s+{_PRESENCE_WORDS}\b",
        rf"\b{t}\b(?:\s+\w+){{0,3}}\s+{_ABSENCE_WORDS}\b",
    ]
    return re.compile("|".join(patterns))


def _segments(text):
    # Sentence-level split hi kaafi hai ab — templates already word-window
    # limited hain, isliye clause-splitting ki zarurat nahi.
    return re.split(r"[.!?\n]|(?:\s*\*\s*)", text)


def verify_output(ai_text, confirmed_terms):
    """
    ai_text: AI ne jo bhi text generate kiya (summary, translation, ya
             chatbot reply) — plain text ya HTML dono chalega
    confirmed_terms: retriever.py se aaye retrieved_terms list
                      (jinme har item me "term" key hai)

    Returns: {
        "passed": bool,                # True agar koi contradiction/miss nahi mila
        "checked_count": int,          # kitne (non-benign) terms check kiye
        "failed_terms": [str, ...],    # combined (backward-compatible)
        "contradicted_terms": [str, ...],   # term mentioned hua par negate ho gaya
        "not_mentioned_terms": [str, ...],  # term output me kahin nahi mila
    }
    """
    if not confirmed_terms or not ai_text:
        return {
            "passed": True,
            "checked_count": 0,
            "failed_terms": [],
            "contradicted_terms": [],
            "not_mentioned_terms": [],
        }

    clean_text = re.sub(r"<[^>]+>", " ", str(ai_text))  # HTML tags hata do
    text_lower = clean_text.lower()
    segments = [s.lower().strip() for s in _segments(text_lower) if s and s.strip()]

    contradicted_terms = []
    not_mentioned_terms = []
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
        term_mentioned = _term_in_segment(term, text_lower)

        if not term_mentioned:
            not_mentioned_terms.append(item.get("term", ""))
            continue

        contradiction_re = _build_contradiction_regex(term)
        for seg in segments:
            seg = seg.strip()
            if seg and contradiction_re.search(seg):
                contradicted_terms.append(item.get("term", ""))
                break

    failed_terms = list(set(contradicted_terms) | set(not_mentioned_terms))

    return {
        "passed": len(failed_terms) == 0,
        "checked_count": checked_count,
        "failed_terms": failed_terms,
        "contradicted_terms": list(set(contradicted_terms)),
        "not_mentioned_terms": list(set(not_mentioned_terms)),
    }