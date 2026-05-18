import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

_NULL_PRICE_VALUES = frozenset({"", "n/a", "na", "null", "none", "-", "—"})


def normalizar_precio(value: Any) -> int | None:
    """Convierte precios de Gemini a entero o None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().lower()
    if text in _NULL_PRICE_VALUES:
        return None
    cleaned = re.sub(r"[^\d]", "", text)
    if not cleaned:
        return None
    return int(cleaned)


RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "categoria": {"type": "string"},
            "producto": {"type": "string"},
            "presentacion": {"type": "string"},
            "cantidad": {"type": "integer"},
            "unidad": {"type": "string"},
            "precio_extra": {"type": "integer"},
            "precio_primera": {"type": "integer"},
            "precio_por_unidad": {"type": "integer"},
            "variacion": {"type": "string"},
        },
        "required": ["producto"],
    },
}


class FilaBoletin(BaseModel):
    categoria: str | None = None
    producto: str
    presentacion: str | None = None
    cantidad: int | None = None
    unidad: str | None = None
    precio_extra: int | None = None
    precio_primera: int | None = None
    precio_por_unidad: int | None = None
    variacion: str | None = None

    @field_validator("producto")
    @classmethod
    def producto_no_vacio(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("producto no puede estar vacío")
        return str(value).strip()

    @field_validator("cantidad", mode="before")
    @classmethod
    def parse_cantidad(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            text = value.strip()
            if text.lower() in _NULL_PRICE_VALUES:
                return None
            value = int(re.sub(r"[^\d]", "", text) or "0")
        cantidad = int(value)
        if cantidad < 0:
            raise ValueError("cantidad debe ser >= 0")
        return cantidad

    @field_validator(
        "precio_extra",
        "precio_primera",
        "precio_por_unidad",
        mode="before",
    )
    @classmethod
    def parse_precios(cls, value: Any) -> int | None:
        return normalizar_precio(value)

    def to_bq_row(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def validar_lote(
    registros: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Valida filas y devuelve (válidas, errores con índice)."""
    validas: list[dict] = []
    errores: list[dict] = []

    for index, raw in enumerate(registros):
        try:
            fila = FilaBoletin.model_validate(raw)
            validas.append(fila.to_bq_row())
        except Exception as exc:
            errores.append({"index": index, "error": str(exc), "raw": raw})

    return validas, errores
