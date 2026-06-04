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


def retrieve_relevant_info(report_text):

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    data_path = os.path.join(base_dir, "data", "knowledge_base.json")

    with open(data_path, "r", encoding="utf-8") as file:
        knowledge_base = json.load(file)

    found_terms = []
    found_ids = set()  # ← prevent duplicates if main term AND synonym both match

    report_lower = report_text.lower()

    for item in knowledge_base:

        term = item.get("term", "").lower()
        meaning = item.get("patient_explanation", "")
        item_id = item.get("id", term)

        # ← Build full list of terms to check: main term + synonyms + related_terms
        all_variants = [term]
        all_variants += [s.lower() for s in item.get("synonyms_in_report", [])]
        all_variants += [r.lower() for r in item.get("related_terms", [])]

        for variant in all_variants:
            if variant in report_lower and not is_negated(variant, report_lower):
                if item_id not in found_ids:
                    found_ids.add(item_id)
                    found_terms.append({
                        "term": item.get("term", ""),  # always show main term
                        "meaning": meaning
                    })
                break  # ← found a match for this item, no need to check more variants

    return found_terms