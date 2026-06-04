import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_with_groq(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """
You are a professional radiology explanation assistant for patients.
Explain reports clearly, calmly, and accurately.
Do not diagnose.
Do not say 'Dear patient'.
Do not write email style.
Do not use greetings or signatures.
Always structure the answer with headings.
IMPORTANT: If the prompt includes a list of detected terms, your explanation MUST be consistent with ALL of them.
Never say a finding is absent or normal if it appears in the detected terms list.
Do not contradict the detected terms under any circumstances.
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        max_tokens=700
    )

    return response.choices[0].message.content