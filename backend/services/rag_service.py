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

        context_lines.append(
            f"{term}: {meaning}"
        )

    context = "\n".join(context_lines)

    prompt = f"""
You are a radiology report explanation assistant for normal patients.

Main goal:
Explain the report in a very simple, calm, patient-friendly way.

Rules:
- Use simple English only
- Use short bullet points
- Do not diagnose
- Do not give treatment or medicine advice
- Do not exaggerate
- Avoid scary wording
- Avoid email style
- Use only the radiology report and retrieved medical context
- If something is normal, say it is reassuring
- Explain like the reader is not from a medical background
- Keep each bullet short and easy to understand

Radiology Report:
{report_text}

Retrieved Medical Context:
{context}

Return the answer ONLY in this HTML format:

<div class="ai-output">

    <div class="risk-box">
        <h3>Risk Level: Low / Medium / High</h3>
        <p>Explain the risk level in one simple sentence.</p>
    </div>

    <h3>Simple Summary</h3>
    <ul>
        <li>Give the main meaning of the report in simple words.</li>
        <li>Mention reassuring normal findings if present.</li>
        <li>Mention what may need doctor discussion.</li>
    </ul>

    <h3>Important Findings</h3>
    <ul>
        <li><strong>Finding:</strong> explain simply.</li>
        <li><strong>Finding:</strong> explain simply.</li>
    </ul>

    <h3>Medical Terms Explained</h3>
    <ul>
        <li><strong>Term:</strong> easy meaning.</li>
        <li><strong>Term:</strong> easy meaning.</li>
    </ul>

    <h3>What This Means For The Patient</h3>
    <ul>
        <li>Explain what the patient should understand.</li>
        <li>Do not give diagnosis or treatment.</li>
    </ul>

    <h3>Doctor Follow-Up</h3>
    <ul>
        <li>Say the patient should discuss the report with a doctor.</li>
    </ul>

</div>

Important output rules:
- Do not use markdown
- Do not write ##
- Do not write ```html
- Do not add text outside the HTML
"""

    ai_summary = generate_with_provider(prompt, provider)

    # Clean markdown code blocks if model adds them
    ai_summary = ai_summary.strip()
    ai_summary = ai_summary.replace("```html", "")
    ai_summary = ai_summary.replace("```HTML", "")
    ai_summary = ai_summary.replace("```Html", "")
    ai_summary = ai_summary.replace("```", "")
    ai_summary = ai_summary.strip()

    return {
        "summary": ai_summary,
        "findings": findings,
        "terms": retrieved_terms,
        "provider": provider,
        "question": user_question
    }