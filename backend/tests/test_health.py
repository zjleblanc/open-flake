from app.api.health import liveness


async def test_liveness():
    result = await liveness()
    assert result["status"] == "ok"
