import re
import json
from services.retriever import retrieve_relevant_info, find_term_positions
from services.llm_router import generate_with_provider
from services.output_verifier import verify_output


def _convert_to_html(text):
    """Convert plain text/markdown into clean HTML."""

    if '<h3>' in text and '<li>' in text:
        text = re.sub(r'Stop immediately.*', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'Important output rules.*', '', text, flags=re.DOTALL | re.IGNORECASE)
        last_div = text.rfind('</div>')
        if last_div != -1:
            text = text[:last_div + 6]
        return text.strip()

    lines  = text.split('\n')
    output = ['<div class="ai-output">']
    in_ul  = False

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

        if any(x in line.lower() for x in [
            'stop immediately', 'do not add', 'return only',
            'important output', 'confirmed detected', 'must acknowledge'
        ]):
            continue

        heading_match = re.match(r'^\*\*(.+?)\*\*:?$', line) or \
                        re.match(r'^#+\s+(.+)', line)

        if heading_match:
            if in_ul:
                output.append('</ul>')
                in_ul = False
            raw_heading = heading_match.group(1).strip().rstrip(':')
            normalized = heading_map.get(raw_heading.lower(), raw_heading)
            output.append(f'<h3>{normalized}</h3>')

        elif re.match(r'^[\*\-\d]+[\.\)]\s+', line) or re.match(r'^\*\s', line):
            if not in_ul:
                output.append('<ul>')
                in_ul = True
            content = re.sub(r'^[\*\-\d]+[\.\)]\s+', '', line)
            content = re.sub(r'^\*\s', '', content)
            content = re.sub(r'^[•·]\s*', '', content)      
            content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
            output.append(f'  <li>{content}</li>')

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


def _filter_terms_actually_in_report(report_text, retrieved_terms):
    """
    Keep only terms that are ACTUALLY present in report_text (the main
    term or a matched synonym). This prevents retriever false-positive
    matches from being surfaced as a "confirmed finding" in the AI
    summary or highlighting.
    """
    report_lower = report_text.lower()
    verified = []

    for item in retrieved_terms:
        matched_text = item.get("matched_text", "") or item.get("term", "")
        if matched_text.lower().strip() in report_lower:
            verified.append(item)

    return verified


def _get_language_instruction(language):
    """
    Give the AI a language instruction based on the selected language.
    Hinglish is a special casual style, other languages are handled normally.
    """
    if not language or language.strip().lower() == "english":
        return "Write your entire response in English."

    if language.strip().lower() == "hinglish":
        return (
            "Write your ENTIRE response in Hinglish — a casual mix of Hindi "
            "and English, the way young Indians speak in everyday conversation. "
            "Example style: 'Aapka heart normal se thoda bada hai, but tension "
            "lene ki zaroorat nahi hai.' Keep all section headings, bullet points, "
            "and explanations in this Hinglish style. Keep it friendly and easy "
            "to understand."
        )

    return (
        f"Write your ENTIRE response in {language} language, including all "
        f"section headings, bullet points, and explanations. Do not use English "
        f"except for medical terms that don't have a common {language} equivalent."
    )


def get_length_instruction(answer_length):
    """
    Controls how long the response should be, based on the
    selected Answer Length setting.
    """
    mapping = {
        "brief": (
            "Keep the response VERY SHORT. Use only 1 short bullet point per "
            "section. Maximum 8-10 words per bullet. Be extremely concise."
        ),
        "standard": (
            "Use a moderate length response. 2-4 bullet points per section, "
            "each bullet 1-2 sentences long."
        ),
        "intensive": (
            "Provide a thorough, detailed, clinical-style response. For EVERY "
            "finding quoted from the report, give a technical 'What it means' "
            "explanation followed by a simple 'In plain language' explanation. "
            "Do not skip any finding, including normal/negative findings. Be "
            "comprehensive — this should read like a detailed patient education "
            "document, not a quick summary."
        ),
    }
    return mapping.get((answer_length or "standard").lower(), mapping["standard"])


def get_detail_instruction(detail_level):
    """
    Controls how technical/deep the explanation should be, based on
    the selected Detail Level setting.
    """
    mapping = {
        "basic": (
            "Use very simple, everyday words only. Avoid all medical "
            "terminology in explanations — describe things the way you'd "
            "explain to a child or someone with zero medical knowledge."
        ),
        "medium": (
            "Use simple language but you may mention the medical term once "
            "alongside its plain-language meaning. Balance clarity with "
            "enough detail to be genuinely useful."
        ),
        "high": (
            "Provide more comprehensive explanations. You may include "
            "additional relevant context (e.g. why a finding matters, common "
            "causes, what typically happens next) while still keeping "
            "language patient-friendly and avoiding diagnosis."
        ),
    }
    return mapping.get((detail_level or "medium").lower(), mapping["medium"])


def _translate_findings_and_terms(findings, retrieved_terms, language, provider, ollama_model):
    """
    Also translates the findings list and term meanings — these come
    straight from knowledge_base.json in English, so they need to be
    translated separately via the AI.
    Returns: (translated_findings, translated_terms)
    """
    if not language or language.strip().lower() == "english":
        return findings, retrieved_terms

    if not findings and not retrieved_terms:
        return findings, retrieved_terms

    language_instruction = _get_language_instruction(language)

    payload = {
        "findings": findings,
        "terms": [
            {"term": item.get("term", ""), "meaning": item.get("meaning", "")}
            for item in retrieved_terms
        ]
    }

    translate_prompt = f"""Translate ONLY the text values in this JSON into the target language below.

{language_instruction}

STRICT RULES:
- Output MUST be valid JSON only.
- Do NOT include any explanation, preamble, or text before or after the JSON.
- Do NOT wrap the JSON in markdown code fences.
- Keep the JSON structure EXACTLY the same (same keys, same array order, same number of items).
- Only translate the "findings" array text and the "meaning" field inside "terms".
- Keep the "term" field (medical term name) UNCHANGED — do not translate it.

JSON to translate:
{json.dumps(payload, ensure_ascii=False)}

Respond with ONLY the translated JSON object, starting with {{ and ending with }}.
"""

    try:
        raw = generate_with_provider(
            translate_prompt,
            provider,
            detected_terms=[],
            ollama_model=ollama_model
        )

        if not raw:
            return findings, retrieved_terms

        raw = str(raw).strip()
        raw = raw.replace("```json", "").replace("```JSON", "").replace("```", "")
        first_brace = raw.find("{")
        last_brace  = raw.rfind("}")

        if first_brace == -1 or last_brace == -1 or last_brace < first_brace:
            return findings, retrieved_terms

        json_str = raw[first_brace:last_brace + 1]
        translated = json.loads(json_str)

        translated_findings   = translated.get("findings", findings)
        translated_terms_raw  = translated.get("terms", [])

        translated_terms = []
        for i, item in enumerate(retrieved_terms):
            new_item = dict(item)
            if i < len(translated_terms_raw):
                new_item["meaning"] = translated_terms_raw[i].get("meaning", item.get("meaning", ""))
            translated_terms.append(new_item)

        if len(translated_findings) != len(findings):
            translated_findings = findings
        if len(translated_terms) != len(retrieved_terms):
            translated_terms = retrieved_terms

        return translated_findings, translated_terms

    except Exception as e:
        print(f"⚠️ Translation failed with error: {e}")
        return findings, retrieved_terms


def generate_explanation(
    report_text,
    provider="ollama",
    user_question="",
    ollama_model="llama3.2:1b",
    language="English",
    answer_length="standard",
    detail_level="medium",
    allow_fallback=True,
):

    raw_retrieved_terms = retrieve_relevant_info(report_text)

    # SAFETY FILTER — keep only terms that are actually present in the report
    retrieved_terms = _filter_terms_actually_in_report(report_text, raw_retrieved_terms)

    # ── HIGHLIGHTING — original English report par positions nikalo, ──
    # ── translation se pehle, kyunki positions original text ke hisaab se hain ──
    highlighted_terms = find_term_positions(report_text, retrieved_terms)

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

    language_instruction = _get_language_instruction(language)
    length_instruction    = get_length_instruction(answer_length)
    detail_instruction    = get_detail_instruction(detail_level)
    is_intensive          = (answer_length or "standard").lower() == "intensive"

    # Simple plain-text prompt for small local models
    is_small_model = (provider == "ollama" and ollama_model in ["llama3.2:1b", "llama3.2:3b"])

    if is_small_model:
        prompt = f"""You are a helpful assistant explaining a radiology report to a patient in simple language.

IMPORTANT LANGUAGE INSTRUCTION: {language_instruction}
IMPORTANT LENGTH INSTRUCTION: {length_instruction}
IMPORTANT DETAIL LEVEL INSTRUCTION: {detail_instruction}

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
        if is_intensive:
            output_format = """
<div class="ai-output">

    <h3>Understanding Your Report</h3>
    <ul>
        <li>A brief intro to what kind of report this is and what it's used for.</li>
    </ul>

    <h3>What the Findings Mean</h3>
    <ul>
        <li><strong>"[exact finding quoted from the report]":</strong> What it means: [technical explanation of the term]. In plain language: [simple, everyday explanation].</li>
        <li>Repeat this pattern for EVERY finding in the report, including normal/negative findings (e.g. "no fracture", "no pneumothorax") — do not skip any.</li>
    </ul>

    <h3>Impression (Summary of Key Findings)</h3>
    <ul>
        <li>Restate each impression/summary point from the report in plain language.</li>
    </ul>

    <h3>Overall Meaning of Your Report</h3>
    <ul>
        <li>What these findings together suggest for the patient, in plain non-diagnostic language.</li>
    </ul>

    <h3>Next Steps</h3>
    <ul>
        <li>What the patient can expect their doctor to discuss, check, or recommend next.</li>
    </ul>

</div>
"""
        else:
            output_format = """
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

        prompt = f"""
You are a radiology report explanation assistant for normal patients.

Rules:
- Use simple language only
- Do not diagnose
- Do not give treatment or medicine advice
- Explain like the reader has no medical background
- CRITICAL: Every term in Confirmed Detected Terms MUST appear as a real finding
- IMPORTANT LANGUAGE INSTRUCTION: {language_instruction}
- IMPORTANT LENGTH INSTRUCTION: {length_instruction}
- IMPORTANT DETAIL LEVEL INSTRUCTION: {detail_instruction}

Radiology Report:
{report_text}

Medical Context:
{context}

{confirmed_terms_block}

Return ONLY this HTML, nothing else (but write the actual text content in the language specified above, following the length and detail instructions):
{output_format}
"""

    ai_summary = generate_with_provider(
        prompt,
        provider,
        detected_terms=retrieved_terms,
        ollama_model=ollama_model,
        allow_fallback=allow_fallback
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

    ai_summary = _convert_to_html(ai_summary)

    findings, retrieved_terms = _translate_findings_and_terms(
        findings, retrieved_terms, language, provider, ollama_model
    )

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

    verification = verify_output(ai_summary, retrieved_terms)

    return {
        "summary":           ai_summary,
        "risk_level":        risk_level,
        "risk_reason":       "Based on the report findings.",
        "findings":          findings,
        "terms":             retrieved_terms,
        "detected_terms":    retrieved_terms,
        "provider":          provider,
        "question":          user_question,
        "verification":      verification,
        "highlighted_terms": highlighted_terms,
    }