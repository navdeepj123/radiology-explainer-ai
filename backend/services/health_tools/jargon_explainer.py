from services.health_tools.base_tool import BaseHealthTool


class JargonExplainerTool(BaseHealthTool):
    tool_id = "jargon_explainer"
    tool_name = "Medical Jargon Explainer"

    def validate_input(self) -> bool:
        term = self.user_input.get("term", "").strip()
        if not term:
            self.errors.append("Field 'term' is required.")
            return False
        return True

    def build_prompt(self) -> str:
        term = self.user_input["term"].strip()
        return (
            f"You are a medical communication assistant. Explain the following "
            f"medical term in simple, plain language for a patient with no medical "
            f"background. Keep it under 100 words. Do not add extra findings or "
            f"information not related to the term.\n\n"
            f"Term: {term}"
        )