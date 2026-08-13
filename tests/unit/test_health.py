from __future__ import annotations


async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["database_connected"] is True
    assert body["dry_run"] is True
    assert "app_env" in body


async def test_health_sets_correlation_id_header(client):
    response = await client.get("/health")
    assert "x-correlation-id" in response.headers
