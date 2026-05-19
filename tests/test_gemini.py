import json
from unittest.mock import MagicMock, patch

import pytest

from app.gemini_service import (
    _build_generation_config,
    _parse_gemini_json,
    extraer_registros,
    reset_vertex,
)


def test_build_generation_config_disables_thinking():
    config = _build_generation_config()
    thinking = config._raw_generation_config.thinking_config
    assert thinking is not None
    assert thinking.thinking_budget == 0


def test_parse_gemini_json_markdown():
    raw = '```json\n[{"producto": "Tomate"}]\n```'
    data = _parse_gemini_json(raw)
    assert len(data) == 1
    assert data[0]["producto"] == "Tomate"


def test_parse_gemini_json_not_array():
    with pytest.raises(ValueError, match="array"):
        _parse_gemini_json('{"producto": "Tomate"}')


@patch("app.gemini_service.GenerativeModel")
@patch("app.gemini_service.init_vertex")
def test_extraer_registros(mock_init, mock_model_cls):
    reset_vertex()
    mock_response = MagicMock()
    mock_response.text = json.dumps([{"producto": "Papa", "cantidad": 1}])
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    registros, modelo = extraer_registros("gs://bucket/boletin.pdf", use_fallback=False)
    assert len(registros) == 1
    assert modelo == "gemini-2.5-flash"
    mock_init.assert_called()
