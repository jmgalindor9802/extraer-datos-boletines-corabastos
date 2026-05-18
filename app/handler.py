import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from app.bigquery_service import get_client, insertar_filas, ya_procesado
from app.config import GCS_FINALIZED_EVENT, get_settings
from app.events import GcsEvent, parse_gcs_event
from app.fecha import FechaNotFoundError, extraer_fecha_del_nombre
from app.gemini_service import extraer_registros
from app.logging_utils import log_event
from app.models import validar_lote

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HandlerResult:
    message: str
    status_code: int
    metric_event: str
    skipped: bool = False


def _is_pdf(name: str) -> bool:
    return name.lower().endswith(".pdf")


def _should_process_event(event: GcsEvent) -> bool:
    if event.event_type is None:
        return True
    return event.event_type == GCS_FINALIZED_EVENT


def process_event(envelope: dict) -> HandlerResult:
    """Orquesta el flujo completo sin dependencias de Flask."""
    start = time.perf_counter()
    settings = get_settings()

    if not settings.gcp_project or not settings.bq_table:
        return HandlerResult(
            "Configuración incompleta: GCP_PROJECT y BQ_TABLE son obligatorios.",
            500,
            "error",
        )

    try:
        gcs_event = parse_gcs_event(envelope)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            str(exc),
            metric_event="error",
            error_type="parse_event",
        )
        return HandlerResult(f"Error al parsear el evento: {exc}", 400, "error")

    bucket, name = gcs_event.bucket, gcs_event.name
    log_fields = {
        "bucket": bucket,
        "archivo_origen": name,
        "event_type": gcs_event.event_type,
    }

    if settings.allowed_bucket and bucket != settings.allowed_bucket:
        log_event(
            logger,
            logging.WARNING,
            "Bucket no permitido.",
            metric_event="error",
            **log_fields,
        )
        return HandlerResult(f"Bucket no permitido: {bucket}", 403, "error")

    if not _should_process_event(gcs_event):
        log_event(
            logger,
            logging.INFO,
            "Evento ignorado (tipo no finalized).",
            metric_event="skipped",
            skipped=True,
            skip_reason="event_type",
            **log_fields,
        )
        return HandlerResult(
            f"Evento ignorado: {gcs_event.event_type}", 200, "skipped", skipped=True
        )

    if settings.require_pdf and not _is_pdf(name):
        log_event(
            logger,
            logging.INFO,
            "Archivo ignorado (no es PDF).",
            metric_event="skipped",
            skipped=True,
            skip_reason="not_pdf",
            **log_fields,
        )
        return HandlerResult(f"Archivo ignorado (no PDF): {name}", 200, "skipped", skipped=True)

    try:
        fecha = extraer_fecha_del_nombre(name, strict=settings.strict_fecha)
    except FechaNotFoundError as exc:
        log_event(
            logger,
            logging.ERROR,
            str(exc),
            metric_event="error",
            error_type="fecha",
            **log_fields,
        )
        return HandlerResult(str(exc), 422, "error")

    client = get_client()

    if settings.skip_if_processed and ya_procesado(
        client, settings.bq_table, name
    ):
        log_event(
            logger,
            logging.INFO,
            "Archivo ya procesado.",
            metric_event="skipped",
            skipped=True,
            skip_reason="already_processed",
            **log_fields,
        )
        return HandlerResult(
            f"ya procesado: {name}", 200, "skipped", skipped=True
        )

    gcs_uri = f"gs://{bucket}/{name}"
    inserted_at = datetime.now(timezone.utc).isoformat()

    try:
        registros_raw, modelo_usado = extraer_registros(gcs_uri, use_fallback=False)
        validas, errores = validar_lote(registros_raw)

        if not validas:
            log_event(
                logger,
                logging.WARNING,
                "Validación falló con modelo principal; intentando fallback.",
                metric_event="fallback",
                filas_raw=len(registros_raw),
                errores_validacion=len(errores),
                **log_fields,
            )
            registros_raw, modelo_usado = extraer_registros(
                gcs_uri, use_fallback=True
            )
            validas, errores = validar_lote(registros_raw)

        if not validas:
            log_event(
                logger,
                logging.ERROR,
                "Sin filas válidas tras fallback.",
                metric_event="error",
                error_type="validation",
                errores_validacion=errores,
                **log_fields,
            )
            return HandlerResult(
                "No se obtuvieron filas válidas tras procesar el PDF.",
                422,
                "error",
            )

    except json.JSONDecodeError as exc:
        log_event(
            logger,
            logging.ERROR,
            f"JSON inválido: {exc}",
            metric_event="error",
            error_type="json_decode",
            **log_fields,
        )
        return HandlerResult(
            f"Error: Gemini devolvió un JSON inválido — {exc}", 422, "error"
        )
    except ValueError as exc:
        log_event(
            logger,
            logging.ERROR,
            str(exc),
            metric_event="error",
            error_type="gemini_value",
            **log_fields,
        )
        return HandlerResult(str(exc), 422, "error")
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            str(exc),
            metric_event="error",
            error_type="gemini",
            **log_fields,
        )
        return HandlerResult(f"Error al procesar con Gemini: {exc}", 500, "error")

    for row in validas:
        row["fecha"] = fecha
        row["archivo_origen"] = name
        row["inserted_at"] = inserted_at
        row["modelo_usado"] = modelo_usado

    try:
        insertar_filas(client, settings.bq_table, validas)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            str(exc),
            metric_event="error",
            error_type="bigquery",
            **log_fields,
        )
        return HandlerResult(f"Error al insertar en BigQuery: {exc}", 500, "error")

    latency_ms = int((time.perf_counter() - start) * 1000)
    msg = f"OK — {len(validas)} registros insertados para fecha {fecha}."
    log_event(
        logger,
        logging.INFO,
        msg,
        metric_event="processed",
        filas_insertadas=len(validas),
        modelo_usado=modelo_usado,
        latency_ms=latency_ms,
        fecha=fecha,
        **log_fields,
    )
    return HandlerResult(msg, 200, "processed")
