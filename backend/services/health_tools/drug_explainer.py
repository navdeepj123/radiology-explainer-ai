from services.health_tools.base_tool import BaseHealthTool


class DrugExplainerTool(BaseHealthTool):
    tool_id = "drug_explainer"
    tool_name = "Drug Explanation Tool"

    def validate_input(self):
        drug_name = self.user_input.get("drug_name", "").strip()
        if not drug_name:
            self.errors.append("Field 'drug_name' is required.")
            return False
        return True

    def build_prompt(self):
        drug_name = self.user_input["drug_name"].strip()
        dosage = self.user_input.get("dosage", "").strip()
        dosage_line = f"They mentioned taking: {dosage}\n" if dosage else ""
        return (
            f"A patient wants to understand a medicine they've been prescribed "
            f"or are taking. Explain it like a caring pharmacist chatting with "
            f"them at the counter — warm, simple, and reassuring.\n\n"
            f"Medicine: {drug_name}\n{dosage_line}\n"
            f"STRICT RULES — follow all of these:\n"
            f"1. NEVER use technical/scientific words (no enzyme names, no "
            f"receptor names, no chemistry, no Latin medical terms).\n"
            f"2. NO tables. NO markdown headers. Use short paragraphs and "
            f"simple bullet points only.\n"
            f"3. Cover, in this order: what it's commonly used for (1-2 "
            f"sentences), a few common side effects in everyday words (as "
            f"bullets), and one simple safety reminder.\n"
            f"4. Keep the whole answer under 130 words.\n"
            f"5. Do NOT give new dosage instructions — only repeat back what "
            f"the patient already told you, if anything.\n"
            f"6. End with one short, friendly line reminding them to check "
            f"with their doctor or pharmacist for anything specific to them."
        )