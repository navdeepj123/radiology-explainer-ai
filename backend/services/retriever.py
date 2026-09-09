import json
import os
import re

# The semantic fallback needs faiss/sentence-transformers (see
# requirements.txt). If they aren't installed, degrade to regex-only
# instead of crashing the whole app/benchmark at import time - the
# call site below already treats a broken embedding_search as "skip".
try:
    from services.embedding_retriever import embedding_search
except ImportError:
    def embedding_search(*args, **kwargs):
        raise RuntimeError("embedding_search unavailable (faiss/sentence-transformers not installed)")


def is_negated(term, text):
    segments = re.split(r'[.!?\n]|(?:\s*\*\s*)', text)

    negation_words = [
        "no ", "not ", "without ", "absent ",
        "negative for ", "no evidence of ",
        "no signs of ", "none ", "neither ",
        "not identified", "not seen",
        "not present", "not noted",
        "not detected", "not found"
    ]

    for segment in segments:
        segment = segment.lower().strip()
        if not segment:
            continue
        if term not in segment:
            continue
        if any(neg in segment for neg in negation_words):
            return True

    return False


def _remove_redundant_term_matches(found_terms):
    """
    Sometimes one term's matched text is fully contained inside
    another, more specific term's matched text (e.g. "pneumothorax"
    inside "tension pneumothorax"). When both match at once, we keep
    only the more specific (longer) finding and drop the generic one,
    so duplicate/redundant findings don't show up.
    """
    sorted_terms = sorted(found_terms, key=lambda x: -len(x["matched_text"]))
    kept = []

    for t in sorted_terms:
        t_text = t["matched_text"].lower()
        is_subsumed = any(
            t_text != k["matched_text"].lower() and t_text in k["matched_text"].lower()
            for k in kept
        )
        if not is_subsumed:
            kept.append(t)

    return kept
def _find_sentence_period(text, start_idx):
    """
    Finds the next sentence-ending period after start_idx, skipping
    decimal points (e.g. "2.1", "0.58") which are not sentence ends.
    """
    idx = start_idx
    while True:
        pos = text.find(".", idx)
        if pos == -1:
            return len(text)
        # agar "." ke turant baad ek digit hai, ye decimal point hai
        if pos + 1 < len(text) and text[pos + 1].isdigit():
            idx = pos + 1
            continue
        return pos


def _rfind_sentence_period(text, before_idx):
    """
    Finds the last sentence-ending period before before_idx, skipping
    decimal points (e.g. "2.1", "0.58") which are not sentence ends.
    """
    search_end = before_idx
    while True:
        pos = text.rfind(".", 0, search_end)
        if pos == -1:
            return -1
        # agar "." ke turant baad ek digit hai, ye decimal point hai
        if pos + 1 < len(text) and text[pos + 1].isdigit():
            search_end = pos
            continue
        return pos

def _extract_context_sentence(matched_variant, report_text):
    """
  Extracts the sentence in which the term was found.

    The body map uses this: if a term is generic (e.g. "lesion", whose
    body_system is "General" and therefore has no fixed entry in
    body_regions.json's term_map), anatomical hints are searched for
    in this sentence to decide an approximate body region.

    Example: "A small area of abnormal signal intensity is present in
    the left frontal white matter" -> this sentence gives the hint
    "white matter" -> head region.
    """
    if not matched_variant or not report_text:
        return ""

    lower = report_text.lower()
    idx = lower.find(matched_variant.lower())

    if idx == -1:
        return ""

    start = max(
        _rfind_sentence_period(lower, idx),
        lower.rfind(";", 0, idx),
        lower.rfind("\n", 0, idx),
        lower.rfind("*", 0, idx),
    ) + 1

    end = _find_sentence_period(lower, idx)

    return report_text[start:end].strip()


def _split_sentences(text):
    """Splits the report into sentences — used for the embedding fallback."""
    if not text:
        return []
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def retrieve_relevant_info(report_text):

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    data_path = os.path.join(base_dir, "data", "knowledge_base.json")

    with open(data_path, "r", encoding="utf-8") as file:
        knowledge_base = json.load(file)

    found_terms = []
    found_ids = set()  # prevent duplicates if main term AND synonym both match

    report_lower = report_text.lower()

    for item in knowledge_base:

        term    = item.get("term", "").lower()
        meaning = item.get("patient_explanation", "")
        item_id = item.get("id", term)

        # Only check main term + actual synonyms. related_terms is NOT
        # used here — it's only "conceptually connected" terms, not
        # real synonyms, and using it for matching caused false
        # positives (e.g. "costophrenic angle blunting" matching
        # through "pleural effusion").
        all_variants = [term]
        all_variants += [s.lower() for s in item.get("synonyms_in_report", [])]

        matched_variant = None
        for variant in all_variants:
            if not variant:
                continue
            # word-boundary (\b) is essential — otherwise short strings
            # like "pe" get falsely matched inside larger words
            # (e.g. "hypertension", "upper", "decompensation")
            pattern = r'\b' + re.escape(variant) + r'\b'
            if re.search(pattern, report_lower) and not is_negated(variant, report_lower):
                matched_variant = variant
                break  # one match is enough for this item

        if matched_variant and item_id not in found_ids:
            found_ids.add(item_id)
            found_terms.append({
                "term":                 item.get("term", ""),
                "meaning":              meaning,
                "severity":             item.get("severity", "Low"),
                "urgency":              item.get("urgency", "Non-urgent"),
                "red_flag":             item.get("red_flag", False),
                "matched_text":         matched_variant,
                "image_url":            item.get("image_url"),
                "all_matched_variants": all_variants,   # used for highlighting all occurrences

                # ── Body-map support ──────────────────────────────────
                # body_system: knowledge_base.json's own field. The body
                # map uses this when there is no direct entry in term_map.
                "body_system":          item.get("body_system", ""),

                # context_sentence: the sentence in the report where the
                # term was found. For generic terms (body_system ==
                # "General"), the body map looks for anatomy hints in
                # this same sentence.
                "context_sentence":     _extract_context_sentence(matched_variant, report_text),

                "match_type":           "exact",
            })

    # Remove redundant matches where one term's matched text is fully
    # contained inside another term's matched text (e.g. "pneumothorax"
    # inside "tension pneumothorax") — keep only the more specific one.
    found_terms = _remove_redundant_term_matches(found_terms)

    # ── Embedding fallback (semantic) ─────────────────────────────────
    #  Only runs on sentences where regex found no match. Every candidate
    # must still pass the negation check — the embedding model itself
    # does not understand negation ("no cardiomegaly" looks just as
    # similar to it as "cardiomegaly").
    matched_terms_lower = {t["term"].lower() for t in found_terms}
    sentences = _split_sentences(report_text)

    for sent in sentences:
        sent_lower = sent.lower()

        already_covered = any(
            t["matched_text"].lower() in sent_lower for t in found_terms
        )
        if already_covered:
            continue

        try:
            candidates = embedding_search(sent)
        except Exception:
            # embedding index missing/broken -> silently skip, regex
            # results stay unaffected
            candidates = []

        for c in candidates:
            term_lower = c["term"].lower()

            if term_lower in matched_terms_lower:
                continue
            if is_negated(term_lower, sent_lower):
                continue

            matched_terms_lower.add(term_lower)
            found_terms.append({
                "term":                 c["term"],
                "meaning":              c.get("patient_explanation", ""),
                "severity":             "Low",
                "urgency":              "Non-urgent",
                "red_flag":             False,
                "matched_text":         sent.strip(),
                "image_url":            None,
                "all_matched_variants": [c["term"]],
                "body_system":          c.get("body_system", ""),
                "context_sentence":     sent.strip(),
                "match_type":           "semantic",
            })

    found_terms = _remove_redundant_term_matches(found_terms)

    return found_terms


def find_term_positions(report_text, matched_terms):
    """
    matched_terms: output of retrieve_relevant_info().
    Returns: [{term, matched_text, start, end, meaning, image_url}, ...]
    The frontend uses this to render clickable highlights in the report text.

    For each term, we search for ALL its variants (not just one) so that
    e.g. "atelectasis" and "atelectatic changes" — written in different
    places in the same report — both get highlighted.
    """
    highlights = []

    for item in matched_terms:
        variants_to_search = item.get("all_matched_variants") or [item.get("matched_text") or item.get("term", "")]

        for variant in variants_to_search:
            if not variant:
                continue
            pattern = re.compile(r'\b' + re.escape(variant) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(report_text):
                highlights.append({
                    "term":         item.get("term", ""),
                    "matched_text": m.group(),
                    "start":        m.start(),
                    "end":          m.end(),
                    "meaning":      item.get("meaning", ""),
                    "image_url":    item.get("image_url"),
                })

    # Remove overlapping highlight matches — keep the longer match first
    highlights.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))
    filtered = []
    last_end = -1
    for h in highlights:
        if h["start"] >= last_end:
            filtered.append(h)
            last_end = h["end"]

    return filtered