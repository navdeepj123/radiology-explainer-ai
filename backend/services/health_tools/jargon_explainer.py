from services.health_tools.base_tool import BaseHealthTool


class JargonExplainerTool(BaseHealthTool):
    tool_id = "jargon_explainer"
    tool_name = "Medical Jargon Explainer"

    def validate_input(self):
        term = self.user_input.get("term", "").strip()
        if not term:
            self.errors.append("Field 'term' is required.")
            return False
        return True

    def build_prompt(self):
        term = self.user_input["term"].strip()
        return (
            f"You are explaining a medical term to a worried patient who has no "
            f"medical background at all. They just heard this word from a doctor "
            f"or read it in a report and want to understand it in the simplest "
            f"way possible.\n\n"
            f"Term to explain: {term}\n\n"
            f"STRICT RULES — follow all of these:\n"
            f"1. Write like you're talking to a friend, not writing a textbook. "
            f"Use everyday words only.\n"
            f"2. NEVER use technical/scientific words to explain the term (no "
            f"biology mechanisms, no Latin/Greek medical roots, no chemistry).\n"
            f"3. NO tables. NO markdown headers (#, ##, ###). NO bullet points — "
            f"just 2-3 short, warm sentences.\n"
            f"4. Use a simple real-life comparison if it helps (e.g. 'like when...').\n"
            f"5. Keep the whole answer under 60 words.\n"
            f"6. Do not add extra sections, disclaimers, or unrelated details — "
            f"just the plain explanation."
        )