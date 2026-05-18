def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_post_invalid_json(client):
    response = client.post("/", data="not-json", content_type="application/json")
    assert response.status_code == 400
