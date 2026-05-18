import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

def generate_with_openai(report_text, context="", language="English"):

    prompt = f"""
You are a medical report explanation assistant.

Explain the radiology report in simple patient-friendly language.

Rules:
- Do not diagnose
- Do not provide treatment advice
- Use simple wording
- Mention doctor consultation
- Also provide translated explanation in {language}

Report:
{report_text}

Retrieved Context:
{context}
"""

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    return response.output_text