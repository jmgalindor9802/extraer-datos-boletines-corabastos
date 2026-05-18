import logging
import os

from flask import Flask, jsonify, request

from app.gemini_service import init_vertex
from app.handler import process_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
_vertex_ready = False


@app.before_request
def _ensure_vertex():
    global _vertex_ready
    if _vertex_ready:
        return
    try:
        init_vertex()
        _vertex_ready = True
    except EnvironmentError:
        pass


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["POST"])
def handle_event():
    envelope = request.get_json(force=True, silent=True)
    if envelope is None:
        return ("Error al parsear el evento: cuerpo JSON vacío o inválido.", 400)

    result = process_event(envelope)
    return (result.message, result.status_code)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
