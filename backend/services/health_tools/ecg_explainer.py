from services.health_tools.base_tool import BaseHealthTool


class ECGExplainerTool(BaseHealthTool):
    tool_id = "ecg_explainer"
    tool_name = "ECG Explainer"

    def validate_input(self) -> bool:
        findings = self.user_input.get("ecg_findings", "").strip()
        if not findings:
            self.errors.append("Field 'ecg_findings' is required.")
            return False
        return True

    def build_prompt(self) -> str:
        findings = self.user_input["ecg_findings"].strip()
        return (
            f"You are a medical communication assistant. Explain the following "
            f"ECG report findings in simple, plain language for a patient. "
            f"Only explain terms that are actually present in the text below — "
            f"do not add findings that are not mentioned.\n\n"
            f"ECG findings: {findings}"
        )