import json
import os

def retrieve_relevant_info(report_text):

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    data_path = os.path.join(base_dir, "data", "knowledge_base.json")

    with open(data_path, "r", encoding="utf-8") as file:
        knowledge_base = json.load(file)

    found_terms = []

    report_lower = report_text.lower()

    for item in knowledge_base:

        term = item.get("term", "")

        meaning = item.get("patient_explanation", "")

        if term.lower() in report_lower:

            found_terms.append({
                "term": term,
                "meaning": meaning
            })

    return found_terms