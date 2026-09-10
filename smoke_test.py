from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

r = client.get("/healthz")
print("healthz:", r.status_code, r.json())

r = client.get("/")
assert r.status_code == 200 and "海龟汤" in r.text
print("index: OK")

r = client.post("/api/rooms", json={"name": "tester"})
code = r.json()["code"]
print("create:", r.status_code, r.json())

with client.websocket_connect(f"/ws/{code}?name=tester") as ws:
    init = ws.receive_json()
    print("ws init:", init["type"], init["room"], "llm_ready=", init["llm"])
    for _ in range(2):
        ws.receive_json()
    ws.send_json({"type": "say", "text": "大家好"})
    chat = ws.receive_json()
    print("ws chat:", chat["type"], chat["role"])

    ws.send_json({"type": "say", "text": "开汤"})
    events = [ws.receive_json() for _ in range(3)]
    types = [e["type"] for e in events]
    bot_msg = next((e for e in events if e.get("role") == "bot"), None)
    assert "game" in types and bot_msg is not None, types
    assert "【汤面】" in bot_msg["text"], bot_msg["text"][:80]
    print("bank start:", types)
    print("surface:", bot_msg["text"].splitlines()[0])

    ws.send_json({"type": "say", "text": "提示"})
    hint = ws.receive_json()
    print("hint:", hint["type"], (hint.get("text") or "")[:40])

print("SMOKE OK")
