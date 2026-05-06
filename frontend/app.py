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
            "summary": "This area is prepared for patient-friendly explanation generated using Local Llama and RAG.",
            "findings": [
                "Key findings from the report will appear here.",
                "Important terms will be explained in simple language.",
                "Retrieved context will support the explanation."
            ],
            "terms": [
                {"term": "Cardiomegaly", "meaning": "Enlarged heart"},
                {"term": "Hemorrhage", "meaning": "Bleeding inside the body"},
                {"term": "Effusion", "meaning": "Fluid collection"}
            ],
            "context": [
                "Relevant medical context from WHO, NIH, Red Cross, or local knowledge base will appear here."
            ]
        }

    return render_template("index.html", report_text=report_text, question=question, results=results)

if __name__ == "__main__":
    app.run(debug=True)