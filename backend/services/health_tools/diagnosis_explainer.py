from services.health_tools.base_tool import BaseHealthTool


class DiagnosisExplainerTool(BaseHealthTool):
    tool_id = "diagnosis_explainer"
    tool_name = "Diagnosis Explainer"

    def validate_input(self):
        diagnosis = self.user_input.get("diagnosis", "").strip()
        if not diagnosis:
            self.errors.append("Field 'diagnosis' is required.")
            return False
        return True

    def build_prompt(self):
        diagnosis = self.user_input["diagnosis"].strip()
        return (
            f"A patient just received this diagnosis and is probably a little "
            f"anxious. Explain it to them like a caring friend would, in the "
            f"simplest possible words.\n\n"
            f"Diagnosis: {diagnosis}\n\n"
            f"STRICT RULES — follow all of these:\n"
            f"1. Start with 2 short, reassuring sentences explaining what this "
            f"diagnosis generally means in plain language.\n"
            f"2. Then give 2-3 short bullet points on what it might mean for "
            f"their daily life (simple, practical, non-scary).\n"
            f"3. NEVER use technical/scientific words (no biology mechanisms, "
            f"no lab-value explanations, no drug names).\n"
            f"4. NO tables. NO markdown headers.\n"
            f"5. Do NOT give a treatment plan, medication advice, or prognosis.\n"
            f"6. Keep the whole answer under 110 words.\n"
            f"7. End with one warm, short line encouraging them to talk it "
            f"through with their doctor."
        )