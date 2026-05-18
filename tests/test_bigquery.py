from unittest.mock import MagicMock, patch

from app.bigquery_service import insertar_filas, ya_procesado


def test_ya_procesado_true():
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([{"f0_": 1}])
    mock_client.query.return_value.result.return_value = mock_result

    assert ya_procesado(mock_client, "proj.ds.table", "boletin.pdf") is True
    mock_client.query.assert_called_once()


def test_ya_procesado_false():
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter([])
    mock_client.query.return_value.result.return_value = mock_result

    assert ya_procesado(mock_client, "proj.ds.table", "boletin.pdf") is False


@patch("app.bigquery_service.get_settings")
def test_insertar_filas_error(mock_settings):
    mock_settings.return_value.bq_table = "proj.ds.table"
    mock_client = MagicMock()
    mock_client.insert_rows_json.return_value = [{"index": 0, "errors": ["fail"]}]

    try:
        insertar_filas(mock_client, "proj.ds.table", [{"producto": "x"}])
        assert False, "debía lanzar RuntimeError"
    except RuntimeError as exc:
        assert "BigQuery" in str(exc)
