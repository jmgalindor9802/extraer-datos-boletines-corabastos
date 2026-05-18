import base64
import json

import pytest

from app.events import parse_gcs_event


def test_direct_gcs_payload():
    event = parse_gcs_event({"bucket": "my-bucket", "name": "boletin_2026-02-16.pdf"})
    assert event.bucket == "my-bucket"
    assert event.name == "boletin_2026-02-16.pdf"


def test_pubsub_wrapper():
    inner = {"bucket": "bkt", "name": "file.pdf"}
    encoded = base64.b64encode(json.dumps(inner).encode()).decode()
    envelope = {"message": {"data": encoded}}
    event = parse_gcs_event(envelope)
    assert event.bucket == "bkt"
    assert event.name == "file.pdf"


def test_proto_payload():
    envelope = {
        "protoPayload": {
            "resourceName": "projects/_/buckets/my-bucket/objects/folder/file.pdf"
        }
    }
    event = parse_gcs_event(envelope)
    assert event.bucket == "my-bucket"
    assert event.name == "folder/file.pdf"


def test_missing_bucket_raises():
    with pytest.raises(ValueError, match="bucket/name"):
        parse_gcs_event({"name": "only-name.pdf"})
