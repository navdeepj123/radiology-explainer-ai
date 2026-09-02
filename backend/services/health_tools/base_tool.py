"""
Generic base class for all AI health tools.
"""

from abc import ABC, abstractmethod
from services.llm_router import generate_with_provider
from services.rag_service import get_length_instruction, get_detail_instruction


class BaseHealthTool(ABC):
    tool_id = None
    tool_name = None
    default_provider = "groq"

    def __init__(self, user_input, provider=None, options=None):
        self.user_input = user_input or {}
        self.provider = provider or self.default_provider
        self.options = options or {}
        self.errors = []

    @abstractmethod
    def validate_input(self):
        raise NotImplementedError

    @abstractmethod
    def build_prompt(self):
        raise NotImplementedError

    def postprocess(self, raw_output):
        return {"result": raw_output}

    def run(self):
        if not self.validate_input():
            return {
                "success": False,
                "tool": self.tool_id,
                "errors": self.errors
            }

        prompt = self.build_prompt()

        length_instr = get_length_instruction(self.options.get("answer_length", "standard"))
        detail_instr = get_detail_instruction(self.options.get("detail_level", "medium"))
        prompt = prompt + f"\n\n{length_instr}\n{detail_instr}"

        try:
            raw_output = generate_with_provider(
                prompt,
                self.provider,
                detected_terms=[],
                ollama_model=self.options.get("ollama_model", "llama3.2:1b"),
            )
        except Exception as e:
            return {
                "success": False,
                "tool": self.tool_id,
                "errors": ["LLM call failed: " + str(e)]
            }

        result = self.postprocess(raw_output)
        result.update({
            "success": True,
            "tool": self.tool_id,
            "tool_name": self.tool_name,
            "provider_used": self.provider,
        })
        return result