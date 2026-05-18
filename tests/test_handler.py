import json
from unittest.mock import MagicMock, patch

import pytest

from app.handler import process_event


def _pdf_event(name="boletin_2026-02-16.pdf", bucket="corabastos-bucket"):
    return {
        "bucket": bucket,
        "name": name,
        "eventType": "google.cloud.storage.object.v1.finalized",
    }


@patch("app.handler.insertar_filas")
@patch("app.handler.ya_procesado", return_value=False)
@patch("app.handler.get_client")
@patch("app.handler.extraer_registros")
def test_handler_success(mock_gemini, mock_client, mock_ya, mock_insert):
    mock_gemini.return_value = (
        [{"producto": "Tomate", "cantidad": 5, "categoria": "FRUTAS"}],
        "gemini-2.5-flash",
    )

    result = process_event(_pdf_event())
    assert result.status_code == 200
    assert "OK" in result.message
    assert result.metric_event == "processed"
    mock_gemini.assert_called_once()
    mock_insert.assert_called_once()
    rows = mock_insert.call_args[0][2]
    assert rows[0]["fecha"] == "2026-02-16"
    assert rows[0]["archivo_origen"] == "boletin_2026-02-16.pdf"
    assert rows[0]["modelo_usado"] == "gemini-2.5-flash"


@patch("app.handler.extraer_registros")
@patch("app.handler.ya_procesado", return_value=True)
@patch("app.handler.get_client")
def test_handler_skip_duplicado(mock_client, mock_ya, mock_gemini):
    result = process_event(_pdf_event())
    assert result.status_code == 200
    assert result.skipped is True
    assert "ya procesado" in result.message
    mock_gemini.assert_not_called()


@patch("app.handler.extraer_registros")
@patch("app.handler.get_client")
def test_handler_skip_not_pdf(mock_client, mock_gemini):
    result = process_event(_pdf_event(name="archivo.tmp"))
    assert result.status_code == 200
    assert result.skipped is True
    mock_gemini.assert_not_called()


@patch("app.handler.get_client")
def test_handler_forbidden_bucket(mock_client, monkeypatch):
    monkeypatch.setenv("ALLOWED_BUCKET", "allowed-only")
    from app.config import reset_settings

    reset_settings()
    result = process_event(_pdf_event(bucket="other-bucket"))
    assert result.status_code == 403


@patch("app.handler.insertar_filas")
@patch("app.handler.ya_procesado", return_value=False)
@patch("app.handler.get_client")
@patch("app.handler.extraer_registros")
def test_handler_fallback_on_invalid_rows(
    mock_gemini, mock_client, mock_ya, mock_insert
):
    invalid = [{"producto": ""}]
    valid = [{"producto": "Tomate", "cantidad": 1}]
    mock_gemini.side_effect = [
        (invalid, "gemini-2.5-flash"),
        (valid, "gemini-2.5-flash"),
    ]

    result = process_event(_pdf_event())
    assert result.status_code == 200
    assert mock_gemini.call_count == 2


@patch("app.handler.extraer_registros")
@patch("app.handler.ya_procesado", return_value=False)
@patch("app.handler.get_client")
def test_handler_422_after_fallback(mock_client, mock_ya, mock_gemini):
    mock_gemini.side_effect = [
        ([{"producto": ""}], "gemini-2.5-flash"),
        ([{"producto": ""}], "gemini-2.5-flash"),
    ]
    result = process_event(_pdf_event())
    assert result.status_code == 422


@patch("app.handler.insertar_filas", side_effect=RuntimeError("BQ down"))
@patch("app.handler.ya_procesado", return_value=False)
@patch("app.handler.get_client")
@patch("app.handler.extraer_registros")
def test_handler_bq_error(mock_gemini, mock_client, mock_ya, mock_insert):
    mock_gemini.return_value = ([{"producto": "Tomate"}], "gemini-2.5-flash")
    result = process_event(_pdf_event())
    assert result.status_code == 500


def test_handler_strict_fecha(monkeypatch):
    monkeypatch.setenv("STRICT_FECHA", "true")
    from app.config import reset_settings

    reset_settings()
    result = process_event(_pdf_event(name="sin_fecha.pdf"))
    assert result.status_code == 422


@patch("app.handler.insertar_filas")
@patch("app.handler.ya_procesado", return_value=False)
@patch("app.handler.get_client")
@patch("app.handler.extraer_registros")
def test_handler_json_decode_error(mock_gemini, mock_client, mock_ya, mock_insert):
    mock_gemini.side_effect = json.JSONDecodeError("err", "doc", 0)
    result = process_event(_pdf_event())
    assert result.status_code == 422
