from services.retriever import retrieve_relevant_info
from services.ollama_service import generate_with_ollama

def generate_explanation(report_text):

    retrieved_terms = retrieve_relevant_info(report_text)

    findings = []
    context_lines = []

    for item in retrieved_terms:

        term = item["term"]
        meaning = item["meaning"]

        findings.append(f"{term} detected in report")

        context_lines.append(
            f"{term}: {meaning}"
        )

    context = "\n".join(context_lines)

    prompt = f"""
    You are a medical assistant.

    Explain this radiology report in simple language for a patient.

    Report:
    {report_text}

    Medical Information:
    {context}

    Keep explanation:
    - short
    - easy to understand
    - non-technical
    """

    ai_summary = generate_with_ollama(prompt)

    return {
        "summary": ai_summary,
        "findings": findings,
        "terms": retrieved_terms
    }