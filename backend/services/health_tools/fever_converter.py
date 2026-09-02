from services.health_tools.base_tool import BaseHealthTool
from services.llm_router import generate_with_provider
from services.rag_service import get_length_instruction, get_detail_instruction


class FeverConverterTool(BaseHealthTool):
    tool_id = "fever_converter"
    tool_name = "Fever Converter"

    def validate_input(self):
        value = self.user_input.get("value")
        unit = self.user_input.get("unit", "").strip().upper()

        if value is None:
            self.errors.append("Field 'value' is required.")
            return False
        try:
            float(value)
        except (TypeError, ValueError):
            self.errors.append("Field 'value' must be a number.")
            return False
        if unit not in ("C", "F"):
            self.errors.append("Field 'unit' must be 'C' or 'F'.")
            return False
        return True

    def build_prompt(self):
        return ""

    def _convert(self, value, unit):
        if unit == "C":
            celsius = value
            fahrenheit = (value * 9 / 5) + 32
        else:
            fahrenheit = value
            celsius = (value - 32) * 5 / 9
        return round(celsius, 1), round(fahrenheit, 1)

    def run(self):
        if not self.validate_input():
            return {"success": False, "tool": self.tool_id, "errors": self.errors}

        value = float(self.user_input["value"])
        unit = self.user_input["unit"].strip().upper()
        celsius, fahrenheit = self._convert(value, unit)

        length_instr = get_length_instruction(self.options.get("answer_length", "standard"))
        detail_instr = get_detail_instruction(self.options.get("detail_level", "medium"))

        prompt = (
            f"A patient's temperature is {celsius}°C ({fahrenheit}°F). "
            f"Explain in plain language whether this is normal, mild fever, "
            f"moderate fever, or high fever, and whether they should seek "
            f"medical attention. Do not give medication advice.\n\n"
            f"{length_instr}\n{detail_instr}"
        )

        try:
            explanation = generate_with_provider(
                prompt,
                self.provider,
                detected_terms=[],
                ollama_model=self.options.get("ollama_model", "llama3.2:1b"),
            )
        except Exception as e:
            explanation = None
            self.errors.append(f"LLM explanation failed: {str(e)}")

        return {
            "success": True,
            "tool": self.tool_id,
            "tool_name": self.tool_name,
            "provider_used": self.provider,
            "result": {
                "celsius": celsius,
                "fahrenheit": fahrenheit,
                "explanation": explanation,
            },
        }