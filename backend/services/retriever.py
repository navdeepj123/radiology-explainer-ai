import json
import os
import re


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
    Kabhi-kabhi ek term ka matched text, doosre zyada specific term ke
    matched text ke andar hi contained hota hai (jaise "pneumothorax"
    "tension pneumothorax" ke andar). Jab dono ek saath match ho jayen,
    hum sirf zyada specific (lamba) wala finding rakhte hain — generic
    wala hata dete hain, taaki duplicate/redundant findings na dikhein.
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


def _extract_context_sentence(matched_variant, report_text):
    """
    Us sentence ko nikalta hai jisme term mila tha.

    Body map ise use karta hai: agar term generic hai (jaise "lesion",
    jiska body_system "General" hai aur isliye body_regions.json ke
    term_map mein uski koi fixed entry nahi hoti), toh is sentence mein
    anatomical hints dhoondh ke approximate region decide kiya jaata hai.

    Example: "A small area of abnormal signal intensity is present in
    the left frontal white matter" -> is sentence se "white matter"
    hint milta hai -> head region.
    """
    if not matched_variant or not report_text:
        return ""

    lower = report_text.lower()
    idx = lower.find(matched_variant.lower())

    if idx == -1:
        return ""

    start = max(
        lower.rfind(".", 0, idx),
        lower.rfind(";", 0, idx),
        lower.rfind("\n", 0, idx),
        lower.rfind("*", 0, idx),
    ) + 1

    end = lower.find(".", idx)
    if end == -1:
        end = len(lower)

    return report_text[start:end].strip()


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
                # body_system: knowledge_base.json ka apna field. Body map
                # ise use karta hai jab term_map mein direct entry na ho.
                "body_system":          item.get("body_system", ""),

                # context_sentence: report ka wo sentence jisme term mila.
                # Generic terms (body_system == "General") ke liye body map
                # isi sentence mein anatomy hints dhoondhta hai.
                "context_sentence":     _extract_context_sentence(matched_variant, report_text),
            })

    # Remove redundant matches where one term's matched text is fully
    # contained inside another term's matched text (e.g. "pneumothorax"
    # inside "tension pneumothorax") — keep only the more specific one.
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