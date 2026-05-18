import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GCS_FINALIZED_EVENT = "google.cloud.storage.object.v1.finalized"

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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    gcp_project: str | None
    gcp_location: str
    bq_table: str | None
    gemini_model: str
    gemini_model_fallback: str
    gemini_thinking_budget: int
    gemini_max_retries: int
    allowed_bucket: str | None
    require_pdf: bool
    strict_fecha: bool
    skip_if_processed: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gcp_project=os.environ.get("GCP_PROJECT"),
            gcp_location=os.environ.get("GCP_LOCATION", "us-central1"),
            bq_table=os.environ.get("BQ_TABLE"),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_model_fallback=os.environ.get(
                "GEMINI_MODEL_FALLBACK", "gemini-2.5-flash"
            ),
            gemini_thinking_budget=_env_int("GEMINI_THINKING_BUDGET", 1024),
            gemini_max_retries=_env_int("GEMINI_MAX_RETRIES", 3),
            allowed_bucket=os.environ.get("ALLOWED_BUCKET") or None,
            require_pdf=_env_bool("REQUIRE_PDF", True),
            strict_fecha=_env_bool("STRICT_FECHA", False),
            skip_if_processed=_env_bool("SKIP_IF_PROCESSED", True),
        )

    def validate(self) -> None:
        if not self.gcp_project:
            logger.error("GCP_PROJECT no está configurado.")
        if not self.bq_table:
            logger.error("BQ_TABLE no está configurado.")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
        _settings.validate()
    return _settings


def reset_settings() -> None:
    """Restablece la configuración (útil en tests)."""
    global _settings
    _settings = None
