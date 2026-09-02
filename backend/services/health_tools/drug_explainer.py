from services.health_tools.base_tool import BaseHealthTool


class DrugExplainerTool(BaseHealthTool):
    tool_id = "drug_explainer"
    tool_name = "Drug Explanation Tool"

    def validate_input(self) -> bool:
        drug_name = self.user_input.get("drug_name", "").strip()
        if not drug_name:
            self.errors.append("Field 'drug_name' is required.")
            return False
        return True

    def build_prompt(self) -> str:
        drug_name = self.user_input["drug_name"].strip()
        dosage = self.user_input.get("dosage", "").strip()
        dosage_line = f"Prescribed dosage: {dosage}\n" if dosage else ""
        return (
            f"You are a medical communication assistant. Explain the medicine "
            f"below in plain language for a patient: what it's commonly used for, "
            f"and general common side effects. End with a note to always follow "
            f"the doctor's prescribed dosage and consult them for concerns. "
            f"Do not give new dosage recommendations.\n\n"
            f"Medicine: {drug_name}\n{dosage_line}"
        )