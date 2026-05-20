from services.retriever import retrieve_relevant_info
from services.llm_router import generate_with_provider

def generate_explanation(report_text, provider="ollama", user_question=""):

    retrieved_terms = retrieve_relevant_info(report_text)

    findings = []
    context_lines = []

    for item in retrieved_terms:
        term = item["term"]
        meaning = item["meaning"]

        findings.append(f"{term} detected in report")
        context_lines.append(f"{term}: {meaning}")

    context = "\n".join(context_lines)

    if user_question.strip():
        task_instruction = f"""
User Question:
{user_question}

Answer the user's question based only on the radiology report and retrieved medical context.
If the question asks about one finding, explain only that finding.
If the question asks for meaning, explain the meaning simply.
If the report does not mention the answer, say it is not mentioned in the report.
Do not repeat the full report explanation unless the user asks for the full report.
"""
    else:
        task_instruction = """
The user has not asked a specific question.
Give a full patient-friendly explanation of the report.
"""

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
- Do not give treatment advice

Radiology Report:
{report_text}

Retrieved Medical Context:
{context}

{task_instruction}

Return format:
Simple Summary:
...

Important Findings:
- ...

Medical Terms Explained:
- ...

Safety Advice:
...
"""

    ai_summary = generate_with_provider(prompt, provider)

    return {
        "summary": ai_summary,
        "findings": findings,
        "terms": retrieved_terms,
        "provider": provider,
        "question": user_question
    }