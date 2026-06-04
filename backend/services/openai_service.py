from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

def generate_with_openai(prompt):

    response = client.chat.completions.create(

        model="openrouter/free",

        messages=[
            {
                "role": "system",
                "content": """
You are a professional radiology explanation assistant for patients.

Rules:
- Use simple English
- Use bullet points
- Use headings
- Do not diagnose
- Do not give treatment advice
- Be patient friendly
- IMPORTANT: If the prompt includes a list of detected terms, your explanation MUST be consistent with ALL of them.
- Never say a finding is absent or normal if it appears in the detected terms list.
- Do not contradict the detected terms under any circumstances.
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.2,
        max_tokens=900
    )

    return response.choices[0].message.content