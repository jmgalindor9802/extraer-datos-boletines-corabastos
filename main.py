import os
import json
import re
import logging
from datetime import datetime

from flask import Flask, request

import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig

from google.cloud import bigquery

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get("GCP_PROJECT")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
BQ_TABLE = os.environ.get("BQ_TABLE")  # formato: project.dataset.table

# ---------------------------------------------------------------------------
# System prompt para Gemini
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Eres un analista de datos. Extrae los datos de las tablas de este boletín de Corabastos.
Devuelve UNICAMENTE un JSON (array de objetos).
Para cada fila, extrae:

- categoria: (Infiere la categoría basada en el título de la página, ej: 'FRUTAS', 'TUBERCULOS', 'LACTEOS').
- producto: (Columna 'Nombre').
- presentacion: (Columna 'Presentación' o 'Empaque', ej: 'BULTO', 'CAJA').
- cantidad: (Columna 'Cantidad', conviértelo a entero).
- unidad: (Columna 'Unidad de medida').
- precio_extra: (Columna 'Precio con calidad extra'. IMPORTANTE: Elimina el signo '$' y las comas ',', devuelve solo el entero. Ej: 16000).
- precio_primera: (Columna 'Precio con calidad primera'. Elimina '$' y ',', devuelve entero).
- precio_por_unidad: (Columna 'Precio cal por unidad' o similar. Elimina '$' y ',', devuelve entero).
- variacion: (Columna 'Variación' o 'Tendencia').

No incluyas texto adicional fuera del JSON. Solo el array de objetos."""


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def extraer_fecha_del_nombre(filename: str) -> str:
    """Intenta extraer la fecha del nombre del archivo.

    Soporta formatos:
      - boletin_2026-02-16.pdf  -> 2026-02-16
      - boletin_20260216.pdf    -> 2026-02-16
      - boletin.2026-02-16.pdf  -> 2026-02-16

    Si no puede extraerla, devuelve la fecha actual.
    """
    # Formato YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # Formato YYYYMMDD
    match = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if match:
        year, month, day = match.group(1), match.group(2), match.group(3)
        # Validar que sea una fecha razonable
        try:
            datetime(int(year), int(month), int(day))
            return f"{year}-{month}-{day}"
        except ValueError:
            pass

    logger.warning(
        "No se pudo extraer la fecha del nombre '%s'. Usando fecha actual.",
        filename,
    )
    return datetime.now().strftime("%Y-%m-%d")


def procesar_con_gemini(gcs_uri: str) -> list[dict]:
    """Envía el PDF a Gemini y devuelve la lista de registros."""
    vertexai.init(project=GCP_PROJECT, location=GCP_LOCATION)

    model = GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )

    pdf_part = Part.from_uri(uri=gcs_uri, mime_type="application/pdf")

    generation_config = GenerationConfig(
        response_mime_type="application/json",
        temperature=0.1,
    )

    logger.info("Enviando PDF a Gemini: %s", gcs_uri)
    response = model.generate_content(
        [pdf_part, "Extrae todos los datos de las tablas de precios de este boletín."],
        generation_config=generation_config,
    )

    raw_text = response.text
    logger.info("Respuesta de Gemini recibida (%d caracteres).", len(raw_text))

    # Parsear JSON —  Gemini puede devolver bloques ```json ... ```
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)

    if not isinstance(data, list):
        raise ValueError(
            f"Se esperaba un array JSON, pero se recibió {type(data).__name__}."
        )

    logger.info("Se extrajeron %d registros del PDF.", len(data))
    return data


def insertar_en_bigquery(rows: list[dict]) -> None:
    """Inserta las filas en BigQuery usando insert_rows_json."""
    if not BQ_TABLE:
        raise EnvironmentError("La variable de entorno BQ_TABLE no está configurada.")

    client = bigquery.Client(project=GCP_PROJECT)

    logger.info("Insertando %d filas en %s …", len(rows), BQ_TABLE)
    errors = client.insert_rows_json(BQ_TABLE, rows)

    if errors:
        logger.error("Errores al insertar en BigQuery: %s", errors)
        raise RuntimeError(f"Errores de inserción en BigQuery: {errors}")

    logger.info("Inserción exitosa en BigQuery.")


# ---------------------------------------------------------------------------
# Endpoint principal (Eventarc / Cloud Run)
# ---------------------------------------------------------------------------
@app.route("/", methods=["POST"])
def handle_event():
    """Procesa el evento de Eventarc (finalized en GCS)."""

    # 1. Parsear el payload del evento -----------------------------------
    try:
        envelope = request.get_json(force=True)

        # Eventarc envía CloudEvents; el payload puede venir directamente
        # o envuelto en un campo "message" (Pub/Sub push).
        if "message" in envelope:
            # Pub/Sub wrapper
            import base64

            message_data = envelope["message"].get("data", "")
            payload = json.loads(base64.b64decode(message_data).decode("utf-8"))
        else:
            payload = envelope

        # Extraer bucket y name del objeto
        # Para CloudEvents directos de GCS:
        #   payload puede tener protoPayload.resourceName o data con bucket/name
        if "bucket" in payload and "name" in payload:
            bucket = payload["bucket"]
            name = payload["name"]
        elif "protoPayload" in payload:
            resource_name = payload["protoPayload"]["resourceName"]
            # formato: projects/_/buckets/BUCKET/objects/NAME
            parts = resource_name.split("/")
            bucket_idx = parts.index("buckets") + 1
            object_idx = parts.index("objects") + 1
            bucket = parts[bucket_idx]
            name = "/".join(parts[object_idx:])
        else:
            # Intentar estructura de Eventarc con CloudEvents
            # El campo "data" puede contener la información del recurso
            data = payload.get("data", payload)
            bucket = data.get("bucket", data.get("bucketId", ""))
            name = data.get("name", data.get("objectId", ""))

        if not bucket or not name:
            raise ValueError(f"No se pudo extraer bucket/name del payload: {payload}")

        logger.info("Evento recibido — bucket: %s, archivo: %s", bucket, name)

    except Exception as exc:
        logger.error("Error al parsear el evento: %s", exc, exc_info=True)
        return (f"Error al parsear el evento: {exc}", 400)

    # 2. Extraer la fecha del nombre del archivo -------------------------
    try:
        fecha = extraer_fecha_del_nombre(name)
        logger.info("Fecha del boletín: %s", fecha)
    except Exception as exc:
        logger.error("Error al extraer la fecha: %s", exc, exc_info=True)
        fecha = datetime.now().strftime("%Y-%m-%d")

    # 3. Procesar con Vertex AI (Gemini) ---------------------------------
    gcs_uri = f"gs://{bucket}/{name}"
    try:
        registros = procesar_con_gemini(gcs_uri)
    except json.JSONDecodeError as exc:
        logger.error("Gemini devolvió un JSON inválido: %s", exc, exc_info=True)
        return (f"Error: Gemini devolvió un JSON inválido — {exc}", 500)
    except Exception as exc:
        logger.error("Error al procesar con Gemini: %s", exc, exc_info=True)
        return (f"Error al procesar con Gemini: {exc}", 500)

    if not registros:
        logger.warning("Gemini no extrajo ningún registro del PDF.")
        return ("No se extrajeron registros del PDF.", 200)

    # 4. Añadir fecha e insertar en BigQuery -----------------------------
    for row in registros:
        row["fecha"] = fecha
        row["archivo_origen"] = name

    try:
        insertar_en_bigquery(registros)
    except Exception as exc:
        logger.error("Error al insertar en BigQuery: %s", exc, exc_info=True)
        return (f"Error al insertar en BigQuery: {exc}", 500)

    msg = f"OK — {len(registros)} registros insertados para fecha {fecha}."
    logger.info(msg)
    return (msg, 200)


# ---------------------------------------------------------------------------
# Punto de entrada local (gunicorn en producción)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
