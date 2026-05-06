from services.retriever import retrieve_relevant_info

def generate_explanation(report_text):
    retrieved_terms = retrieve_relevant_info(report_text)

    findings = []
    terms = []
    explanation_lines = []

    for item in retrieved_terms:
        term = item["term"]
        meaning = item["meaning"]

        findings.append(f"{term} detected in report")
        terms.append({
            "term": term,
            "meaning": meaning
        })
        explanation_lines.append(f"{term} means {meaning}")

    if explanation_lines:
        summary = (
            "In simple words, this report mentions: "
            + " ".join(explanation_lines)
        )
    else:
        summary = (
            "No matching medical terms were found in the current knowledge base. "
            "Please consult a healthcare professional for proper interpretation."
        )

    return {
        "summary": summary,
        "findings": findings,
        "terms": terms
    }