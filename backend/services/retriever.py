import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "knowledge_base.json")


def load_knowledge_base():
    with open(DATA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def retrieve_relevant_info(report_text):
    knowledge_base = load_knowledge_base()
    report_text_lower = report_text.lower()
    results = []

    for item in knowledge_base:
        term = item["term"].lower()

        if term in report_text_lower:
            results.append(item)

    return results