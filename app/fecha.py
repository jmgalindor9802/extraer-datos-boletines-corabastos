import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class FechaNotFoundError(ValueError):
    """No se pudo inferir la fecha del nombre del archivo."""


def extraer_fecha_del_nombre(filename: str, *, strict: bool = False) -> str:
    """Extrae la fecha del nombre del archivo o usa la fecha actual.

    Soporta: boletin_2026-02-16.pdf, boletin_20260216.pdf, boletin.2026-02-16.pdf
    """
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if match:
        year, month, day = match.group(1), match.group(2), match.group(3)
        try:
            datetime(int(year), int(month), int(day))
            return f"{year}-{month}-{day}"
        except ValueError:
            pass

    match = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if match:
        year, month, day = match.group(1), match.group(2), match.group(3)
        try:
            datetime(int(year), int(month), int(day))
            return f"{year}-{month}-{day}"
        except ValueError:
            pass

    if strict:
        raise FechaNotFoundError(
            f"No se pudo extraer la fecha del nombre '{filename}'."
        )

    logger.warning(
        "No se pudo extraer la fecha del nombre '%s'. Usando fecha actual.",
        filename,
    )
    return datetime.now().strftime("%Y-%m-%d")
