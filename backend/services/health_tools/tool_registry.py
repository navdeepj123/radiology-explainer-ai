"""
Central registry mapping tool_id -> Tool class.
Adding a new tool later = one import + one dict entry here. Nothing else changes.
"""

from services.health_tools.jargon_explainer import JargonExplainerTool
from services.health_tools.diagnosis_explainer import DiagnosisExplainerTool
from services.health_tools.drug_explainer import DrugExplainerTool
from services.health_tools.ecg_explainer import ECGExplainerTool
from services.health_tools.fever_converter import FeverConverterTool


TOOL_REGISTRY = {
    "jargon_explainer": JargonExplainerTool,
    "diagnosis_explainer": DiagnosisExplainerTool,
    "drug_explainer": DrugExplainerTool,
    "ecg_explainer": ECGExplainerTool,
    "fever_converter": FeverConverterTool,
}


def get_tool_class(tool_id: str):
    """Returns the Tool class for a given tool_id, or None if not found."""
    return TOOL_REGISTRY.get(tool_id)


def list_tools():
    """Returns list of available tool_ids (used by frontend dropdown)."""
    return list(TOOL_REGISTRY.keys())