"""
Hybrid tool: does deterministic temperature conversion locally (no LLM needed
for math), then calls LLM only to explain severity in plain language.
"""

from services.health_tools.base_tool import BaseHealthTool
from services.llm_router import generate_with_provider


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

        prompt = (
            f"A patient's temperature reading is {celsius}°C ({fahrenheit}°F). "
            f"Talk to them like a caring nurse would, in very simple words.\n\n"
            f"STRICT RULES:\n"
            f"1. In 2-3 short, warm sentences, say whether this is normal, a "
            f"mild fever, a moderate fever, or a high fever — and whether they "
            f"should consider seeing a doctor.\n"
            f"2. If the number looks impossible for a living person (like "
            f"above 45°C or below 30°C), gently say it's probably a measuring "
            f"mistake and suggest they re-check with a working thermometer.\n"
            f"3. NEVER use technical/scientific words.\n"
            f"4. NO tables. NO markdown headers.\n"
            f"5. Do NOT give medication advice.\n"
            f"6. Keep it under 60 words total."
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