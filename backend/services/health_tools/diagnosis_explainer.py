from services.health_tools.base_tool import BaseHealthTool


class DiagnosisExplainerTool(BaseHealthTool):
    tool_id = "diagnosis_explainer"
    tool_name = "Diagnosis Explainer"

    def validate_input(self) -> bool:
        diagnosis = self.user_input.get("diagnosis", "").strip()
        if not diagnosis:
            self.errors.append("Field 'diagnosis' is required.")
            return False
        return True

    def build_prompt(self) -> str:
        diagnosis = self.user_input["diagnosis"].strip()
        return (
            f"You are a medical communication assistant. A patient has received "
            f"the following diagnosis. Explain what it means, in simple plain "
            f"language, what it generally implies, and general next steps to "
            f"discuss with a doctor. Do NOT give a treatment plan or medication "
            f"advice. Only explain based on the text given, don't invent details.\n\n"
            f"Diagnosis: {diagnosis}"
        )