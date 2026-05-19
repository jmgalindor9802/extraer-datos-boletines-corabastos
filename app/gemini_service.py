import json
import logging
import re
import time
import vertexai
from google.api_core import exceptions as gcp_exceptions
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel,
    Part,
)

from app.config import SYSTEM_PROMPT, get_settings
from app.models import RESPONSE_SCHEMA

logger = logging.getLogger(__name__)

_vertex_initialized = False

USER_PROMPT = "Extrae todos los datos de las tablas de precios de este boletín."


def _is_transient_error(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.TooManyRequests,
            gcp_exceptions.InternalServerError,
            gcp_exceptions.DeadlineExceeded,
            ConnectionError,
            TimeoutError,
        ),
    ):
        return True
    message = str(exc).lower()
    return "429" in message or "503" in message or "timeout" in message


def init_vertex() -> None:
    global _vertex_initialized
    if _vertex_initialized:
        return
    settings = get_settings()
    if not settings.gcp_project:
        raise EnvironmentError("GCP_PROJECT no está configurado.")
    vertexai.init(project=settings.gcp_project, location=settings.gcp_location)
    _vertex_initialized = True
    logger.info("Vertex AI inicializado.")


def reset_vertex() -> None:
    """Restablece el flag de init (útil en tests)."""
    global _vertex_initialized
    _vertex_initialized = False


def _build_generation_config() -> GenerationConfig:
    config = GenerationConfig(
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0.1,
    )
    try:
        from google.cloud.aiplatform_v1beta1.types import content as gapic_types

        # Gemini 2.5 Flash activa thinking por defecto; 0 lo desactiva.
        # https://cloud.google.com/vertex-ai/generative-ai/docs/thinking
        config._raw_generation_config.thinking_config = (
            gapic_types.GenerationConfig.ThinkingConfig(thinking_budget=0)
        )
    except (ImportError, AttributeError) as exc:
        logger.warning(
            "No se pudo desactivar thinking (SDK antiguo): %s", exc
        )
    return config


def _parse_gemini_json(raw_text: str) -> list[dict]:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError(
            f"Se esperaba un array JSON, pero se recibió {type(data).__name__}."
        )
    return data


def _generate_raw(
    gcs_uri: str,
    model_name: str,
) -> tuple[list[dict], str]:
    settings = get_settings()
    init_vertex()

    model = GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
    )
    pdf_part = Part.from_uri(uri=gcs_uri, mime_type="application/pdf")
    generation_config = _build_generation_config()

    @retry(
        retry=retry_if_exception(_is_transient_error),
        stop=stop_after_attempt(settings.gemini_max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _call() -> str:
        response = model.generate_content(
            [pdf_part, USER_PROMPT],
            generation_config=generation_config,
        )
        return response.text

    start = time.perf_counter()
    raw_text = _call()
    duration_ms = int((time.perf_counter() - start) * 1000)

    registros = _parse_gemini_json(raw_text)
    logger.info(
        "Respuesta de Gemini procesada.",
        extra={
            "modelo": model_name,
            "filas_raw": len(registros),
            "duracion_ms": duration_ms,
            "gcs_uri": gcs_uri,
        },
    )
    return registros, model_name


def extraer_registros(
    gcs_uri: str,
    *,
    use_fallback: bool = False,
) -> tuple[list[dict], str]:
    """Extrae registros del PDF. Devuelve (registros_raw, modelo_usado)."""
    settings = get_settings()
    model_name = (
        settings.gemini_model_fallback if use_fallback else settings.gemini_model
    )
    logger.info(
        "Enviando PDF a Gemini: %s (modelo=%s)",
        gcs_uri,
        model_name,
    )
    return _generate_raw(gcs_uri, model_name)
