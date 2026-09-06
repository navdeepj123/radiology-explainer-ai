from services.health_tools.base_tool import BaseHealthTool


class ECGExplainerTool(BaseHealthTool):
    tool_id = "ecg_explainer"
    tool_name = "ECG Explainer"

    def validate_input(self):
        findings = self.user_input.get("ecg_findings", "").strip()
        if not findings:
            self.errors.append("Field 'ecg_findings' is required.")
            return False
        return True

    def build_prompt(self):
        findings = self.user_input["ecg_findings"].strip()
        return (
            f"A patient received these ECG (heart tracing) findings and wants "
            f"a simple explanation. Talk to them like a caring nurse would — "
            f"warm, clear, and reassuring where possible.\n\n"
            f"ECG findings: {findings}\n\n"
            f"STRICT RULES — follow all of these:\n"
            f"1. Only explain terms that actually appear in the findings above "
            f"— do not invent or assume anything extra.\n"
            f"2. NEVER use technical/scientific words (no electrical-conduction "
            f"explanations, no anatomy terms beyond 'heart').\n"
            f"3. NO tables. NO markdown headers. Short paragraphs and simple "
            f"bullet points only.\n"
            f"4. Keep the whole answer under 110 words.\n"
            f"5. Do NOT diagnose or suggest treatment.\n"
            f"6. End with one short line encouraging them to discuss the "
            f"results with their doctor."
        )