"""
Static metadata for each tool - used by frontend to render tool cards,
labels, placeholders etc. Pure data, no logic.
"""

TOOLS_CONFIG = {
    "jargon_explainer": {
        "name": "Medical Jargon Explainer",
        "description": "Explains complex medical terms in simple language.",
        "input_fields": [
            {"key": "term", "label": "Medical term / phrase", "type": "text", "required": True}
        ],
    },
    "diagnosis_explainer": {
        "name": "Diagnosis Explainer",
        "description": "Explains a diagnosis in plain, patient-friendly language.",
        "input_fields": [
            {"key": "diagnosis", "label": "Diagnosis text", "type": "textarea", "required": True}
        ],
    },
    "drug_explainer": {
        "name": "Drug Explanation Tool",
        "description": "Explains a medicine, its use, and common side effects.",
        "input_fields": [
            {"key": "drug_name", "label": "Drug name", "type": "text", "required": True},
            {"key": "dosage", "label": "Dosage (optional)", "type": "text", "required": False}
        ],
    },
    "ecg_explainer": {
        "name": "ECG Explainer",
        "description": "Explains ECG report findings in plain language.",
        "input_fields": [
            {"key": "ecg_findings", "label": "ECG findings / report text", "type": "textarea", "required": True}
        ],
    },
    "fever_converter": {
        "name": "Fever Converter",
        "description": "Converts temperature between C/F and explains fever severity.",
        "input_fields": [
            {"key": "value", "label": "Temperature value", "type": "number", "required": True},
            {"key": "unit", "label": "Unit (C or F)", "type": "text", "required": True}
        ],
    },
}