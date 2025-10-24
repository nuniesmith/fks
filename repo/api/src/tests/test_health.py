from fastapi import status
import pytest
import httpx

try:
    from fastapi_main import app  # type: ignore
except ImportError:  # pragma: no cover
    # Fallback if module name resolution changes to package path
    from fks_api.fastapi_main import app  # type: ignore


@pytest.mark.asyncio
async def test_health():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data.get("status") in {"healthy", "ok"}
