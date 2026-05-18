import base64
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class GcsEvent:
    bucket: str
    name: str
    event_type: str | None


def _extract_event_type(payload: dict) -> str | None:
    for key in ("eventType", "type", "event_type"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("eventType", "type"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    return None


def _extract_bucket_name(payload: dict) -> tuple[str, str]:
    if "bucket" in payload and "name" in payload:
        return payload["bucket"], payload["name"]

    if "protoPayload" in payload:
        resource_name = payload["protoPayload"]["resourceName"]
        parts = resource_name.split("/")
        bucket_idx = parts.index("buckets") + 1
        object_idx = parts.index("objects") + 1
        bucket = parts[bucket_idx]
        name = "/".join(parts[object_idx:])
        return bucket, name

    data = payload.get("data", payload)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}
    if not isinstance(data, dict):
        data = {}

    bucket = data.get("bucket", data.get("bucketId", ""))
    name = data.get("name", data.get("objectId", ""))
    return bucket, name


def parse_gcs_event(envelope: dict) -> GcsEvent:
    """Parsea payloads de Eventarc, CloudEvents o Pub/Sub push."""
    if envelope is None:
        raise ValueError("El envelope del evento es nulo.")

    if "message" in envelope:
        message_data = envelope["message"].get("data", "")
        payload = json.loads(base64.b64decode(message_data).decode("utf-8"))
    else:
        payload = envelope

    bucket, name = _extract_bucket_name(payload)
    if not bucket or not name:
        raise ValueError(f"No se pudo extraer bucket/name del payload: {payload}")

    return GcsEvent(
        bucket=bucket,
        name=name,
        event_type=_extract_event_type(payload),
    )
