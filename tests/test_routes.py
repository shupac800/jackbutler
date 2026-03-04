from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from jackbutler.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.anyio
async def test_index(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Jack Butler" in resp.text


@pytest.mark.anyio
async def test_analyze_endpoint(client, c_major_gp5: Path):
    data = c_major_gp5.read_bytes()
    resp = await client.post(
        "/api/analyze",
        files={"file": ("test.gp5", data, "application/octet-stream")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test Song"
    assert len(body["tracks"]) >= 1
    track = body["tracks"][0]
    assert len(track["measures"]) >= 1


@pytest.mark.anyio
async def test_analyze_no_file(client):
    resp = await client.post("/api/analyze")
    assert resp.status_code == 422
