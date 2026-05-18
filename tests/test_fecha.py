from datetime import datetime

import pytest
from freezegun import freeze_time

from app.fecha import FechaNotFoundError, extraer_fecha_del_nombre


def test_fecha_con_guiones():
    assert extraer_fecha_del_nombre("boletin_2026-02-16.pdf") == "2026-02-16"


def test_fecha_compacta():
    assert extraer_fecha_del_nombre("boletin_20260216.pdf") == "2026-02-16"


@freeze_time("2026-05-18 12:00:00")
def test_sin_fecha_usa_hoy():
    assert extraer_fecha_del_nombre("boletin_sin_fecha.pdf") == "2026-05-18"


def test_strict_fecha_falla():
    with pytest.raises(FechaNotFoundError):
        extraer_fecha_del_nombre("boletin_sin_fecha.pdf", strict=True)


def test_fecha_invalida_compacta():
    with pytest.raises(FechaNotFoundError):
        extraer_fecha_del_nombre("boletin_20260299.pdf", strict=True)


def test_fecha_invalida_con_guiones():
    with pytest.raises(FechaNotFoundError):
        extraer_fecha_del_nombre("boletin_2026-13-45.pdf", strict=True)


@freeze_time("2026-05-18 12:00:00")
def test_fecha_invalida_con_guiones_usa_hoy():
    assert extraer_fecha_del_nombre("boletin_2026-13-45.pdf") == "2026-05-18"
