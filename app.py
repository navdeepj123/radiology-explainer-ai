from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    report_text = ""
    question = ""
    results = None

    if request.method == "POST":
        report_text = request.form.get("report_text", "")
        question = request.form.get("question", "")

        results = {
            "explanation": "This section is prepared for AI-generated patient-friendly explanation. Backend will connect this UI with Local Llama and RAG.",
            "findings": [
                "Medical report text received successfully.",
                "Interface is ready to display key findings.",
                "RAG context section is prepared for retrieved medical information."
            ],
            "terms": [
                {"term": "Cardiomegaly", "meaning": "Enlarged heart"},
                {"term": "Hemorrhage", "meaning": "Bleeding inside the body"},
                {"term": "Fracture", "meaning": "Break or crack in a bone"}
            ],
            "context": [
                "Retrieved medical context will appear here from WHO, NIH, or local medical knowledge base.",
                "This section will support the backend RAG output."
            ]
        }

    return render_template("index.html", report_text=report_text, question=question, results=results)

if __name__ == "__main__":
    app.run(debug=True)