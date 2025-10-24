INFINITE = "i=0\nwhile True: i+=1\n"

async def test_times_out(client):  # client is an AsyncClient fixture for the FastAPI app
    r = await client.post("/validate", json={"script": INFINITE, "files": [], "opts": {}})
    assert r.status_code in (408, 422)
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] in ("TIMEOUT", "INTERNAL")
