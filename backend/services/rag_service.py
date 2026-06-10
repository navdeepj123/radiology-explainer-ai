import re
from services.retriever import retrieve_relevant_info
from services.llm_router import generate_with_provider


def _convert_to_html(text):
    """Plain text/markdown ko clean HTML mein convert karo"""

    # Already HTML hai toh clean karke return karo
    if '<h3>' in text and '<li>' in text:
        # leaked instructions hata do
        text = re.sub(r'Stop immediately.*', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'Important output rules.*', '', text, flags=re.DOTALL | re.IGNORECASE)
        last_div = text.rfind('</div>')
        if last_div != -1:
            text = text[:last_div + 6]
        return text.strip()

    # Plain text / markdown → HTML
    lines  = text.split('\n')
    output = ['<div class="ai-output">']
    in_ul  = False

    # Section heading aliases — model ke different heading names normalize karo
    heading_map = {
        'simple summary':           'Simple Summary',
        'summary':                  'Simple Summary',
        'radiology report explanation': 'Simple Summary',
        'report explanation':       'Simple Summary',
        'overview':                 'Simple Summary',
        'important findings':       'Important Findings',
        'findings':                 'Important Findings',
        'key findings':             'Important Findings',
        'detected findings':        'Important Findings',
        'what this means':          'What This Means For The Patient',
        'what this means for the patient': 'What This Means For The Patient',
        'patient information':      'What This Means For The Patient',
        'for the patient':          'What This Means For The Patient',
        'doctor follow-up':         'Doctor Follow-Up',
        'follow-up':                'Doctor Follow-Up',
        'follow up':                'Doctor Follow-Up',
        'next steps':               'Doctor Follow-Up',
        'recommendation':           'Doctor Follow-Up',
    }

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove leaked prompt text
        if any(x in line.lower() for x in [
            'stop immediately', 'do not add', 'return only',
            'important output', 'confirmed detected', 'must acknowledge'
        ]):
            continue

        # ** Heading ** OR # Heading → <h3>
        heading_match = re.match(r'^\*\*(.+?)\*\*:?$', line) or \
                        re.match(r'^#+\s+(.+)', line)

        if heading_match:
            if in_ul:
                output.append('</ul>')
                in_ul = False
            raw_heading = heading_match.group(1).strip().rstrip(':')
            # normalize karo
            normalized = heading_map.get(raw_heading.lower(), raw_heading)
            output.append(f'<h3>{normalized}</h3>')

        # * bullet or - bullet or numbered → <li>
        elif re.match(r'^[\*\-\d]+[\.\)]\s+', line) or re.match(r'^\*\s', line):
            if not in_ul:
                output.append('<ul>')
                in_ul = True
            content = re.sub(r'^[\*\-\d]+[\.\)]\s+', '', line)
            content = re.sub(r'^\*\s', '', content)
            content = re.sub(r'^[•·]\s*', '', content)      
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            output.append(f'  <li>{content}</li>')

        # plain text → li
        else:
            if not in_ul:
                output.append('<ul>')
                in_ul = True
            line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            output.append(f'  <li>{line}</li>')

    if in_ul:
        output.append('</ul>')

    output.append('</div>')
    return '\n'.join(output)


def generate_explanation(report_text, provider="ollama", user_question="", ollama_model="llama3.2:1b"):

    retrieved_terms = retrieve_relevant_info(report_text)

    findings      = []
    context_lines = []

    for item in retrieved_terms:
        term    = item["term"]
        meaning = item["meaning"]
        findings.append(f"{term} detected in report")
        context_lines.append(f"{term}: {meaning}")

    context = "\n".join(context_lines)

    if retrieved_terms:
        confirmed_terms_block = "These terms were CONFIRMED found in the report (mention ALL of them):\n"
        confirmed_terms_block += "\n".join([f"- {item['term']}" for item in retrieved_terms])
    else:
        confirmed_terms_block = "No specific medical terms were detected."

    # ── Small model ke liye simple plain-text prompt ──
    is_small_model = (provider == "ollama" and ollama_model in ["llama3.2:1b", "llama3.2:3b"])

    if is_small_model:
        prompt = f"""You are a helpful assistant explaining a radiology report to a patient in simple language.

Report:
{report_text}

{confirmed_terms_block}

Write a short explanation with these 4 sections using bullet points:

**Simple Summary**
- explain the main findings simply

**Important Findings**
- list each detected term and what it means simply

**What This Means For The Patient**
- what the patient should know

**Doctor Follow-Up**
- tell the patient to discuss with their doctor
"""
    else:
        prompt = f"""
You are a radiology report explanation assistant for normal patients.

Rules:
- Use simple English only
- Use short bullet points
- Do not diagnose
- Do not give treatment or medicine advice
- Explain like the reader has no medical background
- CRITICAL: Every term in Confirmed Detected Terms MUST appear as a real finding

Radiology Report:
{report_text}

Medical Context:
{context}

{confirmed_terms_block}

Return ONLY this HTML, nothing else:

<div class="ai-output">

    <h3>Simple Summary</h3>
    <ul>
        <li>Main meaning in simple words.</li>
        <li>Reassuring normal findings if present.</li>
        <li>What may need doctor discussion.</li>
    </ul>

    <h3>Important Findings</h3>
    <ul>
        <li><strong>Finding:</strong> explain simply.</li>
    </ul>

    <h3>What This Means For The Patient</h3>
    <ul>
        <li>What the patient should understand.</li>
    </ul>

    <h3>Doctor Follow-Up</h3>
    <ul>
        <li>Patient should discuss with a doctor.</li>
    </ul>

</div>
"""

    ai_summary = generate_with_provider(
        prompt,
        provider,
        detected_terms=retrieved_terms,
        ollama_model=ollama_model
    )

    if ai_summary is None:
        ai_summary = """
<div class="ai-output">
    <h3>Simple Summary</h3>
    <ul><li>The AI provider did not return a response. Please try another provider.</li></ul>
</div>
"""

    ai_summary = str(ai_summary).strip()
    ai_summary = ai_summary.replace("```html", "").replace("```HTML", "").replace("```Html", "").replace("```", "")
    ai_summary = ai_summary.strip()

    # ── Convert to clean HTML ──
    ai_summary = _convert_to_html(ai_summary)

    # ── Risk level — dataset ke severity/urgency/red_flag se ──
    risk_level = "Low"

    for item in retrieved_terms:
        red_flag = item.get("red_flag", False)
        urgency  = item.get("urgency",  "Non-urgent")
        severity = item.get("severity", "Low")

        if red_flag or urgency == "Urgent" or severity == "High":
            risk_level = "High"
            break
        elif urgency == "Semi-urgent" or severity == "Medium":
            risk_level = "Medium"

    if risk_level == "Low" and len(retrieved_terms) >= 3:
        risk_level = "Medium"

    return {
        "summary":        ai_summary,
        "risk_level":     risk_level,
        "risk_reason":    "Based on the report findings.",
        "findings":       findings,
        "terms":          retrieved_terms,
        "detected_terms": retrieved_terms,
        "provider":       provider,
        "question":       user_question
    }