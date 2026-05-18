import logging
import re

from google.cloud import bigquery
from google.cloud.bigquery import ScalarQueryParameter

from app.config import get_settings

logger = logging.getLogger(__name__)

_TABLE_PATTERN = re.compile(
    r"^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+$"
)


def _validate_table_id(table: str) -> str:
    if not _TABLE_PATTERN.match(table):
        raise ValueError(f"BQ_TABLE con formato inválido: {table}")
    return table


def get_client() -> bigquery.Client:
    settings = get_settings()
    return bigquery.Client(project=settings.gcp_project)


def ya_procesado(client: bigquery.Client, table: str, archivo_origen: str) -> bool:
    """True si ya existen filas para este archivo_origen."""
    table = _validate_table_id(table)
    query = f"""
        SELECT 1
        FROM `{table}`
        WHERE archivo_origen = @archivo
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            ScalarQueryParameter("archivo", "STRING", archivo_origen),
        ]
    )
    rows = list(client.query(query, job_config=job_config).result())
    return len(rows) > 0


def insertar_filas(client: bigquery.Client, table: str, rows: list[dict]) -> None:
    """Inserta filas en BigQuery vía streaming insert."""
    table = _validate_table_id(table)
    settings = get_settings()

    logger.info("Insertando %d filas en %s …", len(rows), table)
    errors = client.insert_rows_json(table, rows)

    if errors:
        logger.error("Errores al insertar en BigQuery: %s", errors)
        raise RuntimeError(f"Errores de inserción en BigQuery: {errors}")

    logger.info(
        "Inserción exitosa en BigQuery.",
        extra={"filas_insertadas": len(rows), "bq_table": settings.bq_table},
    )
