from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os

from services.rag_service import generate_explanation

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
    static_folder=os.path.join(BASE_DIR, "frontend", "static")
)

CORS(app)

@app.route("/", methods=["GET", "POST"])
def home():

    results = None
    report_text = ""
    question = ""
    provider = "ollama"


    if request.method == "POST":

        report_text = request.form.get("report_text", "")
        question = request.form.get("question", "")
        provider = request.form.get("provider", "ollama")
        
        if report_text:
            results = generate_explanation(report_text, provider)

    return render_template(
        "index.html",
        results=results,
        report_text=report_text,
        question=question,
        provider=provider

    )

if __name__ == "__main__":
    app.run(debug=True, port=5000)