from app.models import FilaBoletin, normalizar_precio, validar_lote


def test_normalizar_precio_con_simbolos():
    assert normalizar_precio("$16,000") == 16000
    assert normalizar_precio("N/A") is None
    assert normalizar_precio(None) is None


def test_fila_boletin_valida():
    fila = FilaBoletin.model_validate(
        {
            "producto": "Papa",
            "categoria": "TUBERCULOS",
            "cantidad": 10,
            "precio_extra": "$1,200",
        }
    )
    assert fila.precio_extra == 1200
    assert fila.cantidad == 10


def test_to_bq_row_omite_none():
    fila = FilaBoletin.model_validate({"producto": "Tomate"})
    row = fila.to_bq_row()
    assert row == {"producto": "Tomate"}
    assert "categoria" not in row
    assert "precio_extra" not in row


def test_validar_lote_mezcla():
    raw = [
        {"producto": "Tomate", "cantidad": 5},
        {"producto": "", "cantidad": -1},
    ]
    validas, errores = validar_lote(raw)
    assert len(validas) == 1
    assert len(errores) == 1
    assert errores[0]["index"] == 1
