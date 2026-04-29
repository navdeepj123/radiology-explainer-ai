from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    report_text = ""
    results = None

    if request.method == "POST":
        report_text = request.form.get("report_text", "")

        results = {
            "summary": "The report contains medical terms. Simple explanations are shown below.",
            "terms": [
                {"term": "Cardiomegaly", "meaning": "Enlarged heart"},
                {"term": "Hemorrhage", "meaning": "Bleeding inside the body"},
                {"term": "Fracture", "meaning": "Break or crack in a bone"}
            ]
        }

    return render_template("index.html", report_text=report_text, results=results)

if __name__ == "__main__":
    app.run(debug=True)