from services.retriever import retrieve_relevant_info


def generate_explanation(report_text):
    retrieved_items = retrieve_relevant_info(report_text)

    if not retrieved_items:
        return {
            "summary": "No known medical terms were found in the current knowledge base.",
            "explanations": []
        }

    explanations = []

    for item in retrieved_items:
        explanations.append({
            "term": item["term"],
            "definition": item["definition"],
            "patient_explanation": item["patient_explanation"]
        })

    return {
        "summary": f"{len(explanations)} medical term(s) found in the report.",
        "explanations": explanations
    }