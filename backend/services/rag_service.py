from services.retriever import retrieve_relevant_info
from services.llm_router import generate_with_provider

def generate_explanation(report_text, provider="ollama"):

    retrieved_terms = retrieve_relevant_info(report_text)

    findings = []
    context_lines = []

    for item in retrieved_terms:
        term = item["term"]
        meaning = item["meaning"]

        findings.append(f"{term} detected in report")
        context_lines.append(f"{term}: {meaning}")

    context = "\n".join(context_lines)

    prompt = f"""
Explain this radiology report for a normal patient.

Rules:
- Use simple English
- Use headings
- Do not diagnose
- Do not exaggerate
- Avoid scary wording
- Avoid email format
- Use only the report and retrieved context
- If something is normal, say it is reassuring
- End with doctor consultation advice

Radiology Report:
{report_text}

Retrieved Medical Context:
{context}

Return exactly in this format:

Simple Summary:
...

Important Findings:
- ...
- ...

Medical Terms Explained:
- ...
- ...

Safety Advice:
...
"""

    ai_summary = generate_with_provider(prompt, provider)

    return {
        "summary": ai_summary,
        "findings": findings,
        "terms": retrieved_terms,
        "provider": provider
    }