from flask import Flask, request, jsonify
from flask_cors import CORS
from services.rag_service import generate_explanation

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Radiology Report Explanation Backend is running",
        "routes": ["/api/test", "/api/test-rag", "/api/explain"]
    })


@app.route("/api/test", methods=["GET"])
def test():
    return jsonify({"message": "Backend is working"})


@app.route("/api/test-rag", methods=["GET"])
def test_rag():
    sample_report = "The scan shows mild cardiomegaly and a lesion. No fracture is seen."
    result = generate_explanation(sample_report)

    return jsonify({
        "original_report": sample_report,
        "summary": result["summary"],
        "explanations": result["explanations"],
        "disclaimer": "This tool is for educational purposes only and does not replace professional medical advice."
    })


@app.route("/api/explain", methods=["POST"])
def explain_report():
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON body is required"}), 400

    report = data.get("report", "")

    if not report.strip():
        return jsonify({"error": "Report text is required"}), 400

    result = generate_explanation(report)

    return jsonify({
        "original_report": report,
        "summary": result["summary"],
        "explanations": result["explanations"],
        "disclaimer": "This tool is for educational purposes only and does not replace professional medical advice."
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)