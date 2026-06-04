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

    # ← Build confirmed terms block to inject into prompt
    if retrieved_terms:
        confirmed_terms_block = "Confirmed Detected Terms (MUST acknowledge ALL of these — do NOT say any are absent or normal):\n"
        confirmed_terms_block += "\n".join([f"- {item['term']}" for item in retrieved_terms])
    else:
        confirmed_terms_block = "No specific medical terms were detected in this report."

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
- CRITICAL: Every term listed under Confirmed Detected Terms MUST appear in your explanation as a real finding

Radiology Report:
{report_text}

Retrieved Medical Context:
{context}

{confirmed_terms_block}

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

    # ← Pass retrieved_terms as detected_terms to enforce consistency
    ai_summary = generate_with_provider(prompt, provider, detected_terms=retrieved_terms)

    if ai_summary is None:
        ai_summary = """
<div class="ai-output">
    <div class="risk-box">
        <h3>Risk Level: Unknown</h3>
        <p>The AI provider did not return a response. Please try another provider.</p>
    </div>
</div>
"""

    ai_summary = str(ai_summary).strip()
    ai_summary = ai_summary.replace("```html", "")
    ai_summary = ai_summary.replace("```HTML", "")
    ai_summary = ai_summary.replace("```Html", "")
    ai_summary = ai_summary.replace("```", "")
    ai_summary = ai_summary.strip()

    risk_level = "Unknown"

    if "Risk Level: High" in ai_summary:
        risk_level = "High"
    elif "Risk Level: Medium" in ai_summary:
        risk_level = "Medium"
    elif "Risk Level: Low" in ai_summary:
        risk_level = "Low"

    return {
        "summary": ai_summary,
        "risk_level": risk_level,
        "risk_reason": "Based on the report findings.",
        "findings": findings,
        "terms": retrieved_terms,
        "detected_terms": retrieved_terms,  # ← added so app.py session storage works
        "provider": provider,
        "question": user_question
    }