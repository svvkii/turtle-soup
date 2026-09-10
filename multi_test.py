import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

from fastapi.testclient import TestClient

import main

with TestClient(main.app) as client:
    h = client.get("/healthz").json()
    code = h["default_room"]
    assert h["rooms"] >= 1, "startup should create default room"
    print("room:", code, "(default)", flush=True)

    with client.websocket_connect(f"/ws/{code}?name=A") as wa:
        print("A connected", flush=True)
        for i in range(3):
            e = wa.receive_json()
            print("A<-", e["type"], flush=True)
        print("--- B connecting", flush=True)
        with client.websocket_connect(f"/ws/{code}?name=B") as wb:
            print("B connected", flush=True)
            for i in range(3):
                e = wb.receive_json()
                print("B<-", e["type"], flush=True)
            for i in range(2):
                e = wa.receive_json()
                print("A<-", e["type"], flush=True)

            wa.send_json({"type": "say", "text": "我先来打个样"})
            print("A said hi", flush=True)
            e1 = wa.receive_json(); print("A<-", e1["type"], e1.get("name"), e1.get("text", "")[:20], flush=True)
            e2 = wb.receive_json(); print("B<-", e2["type"], e2.get("name"), e2.get("text", "")[:20], flush=True)

            wb.send_json({"type": "say", "text": "开汤"})
            print("B started game", flush=True)
            for i in range(3):
                e = wa.receive_json(); print("A<-", e["type"], (e.get("role") or ""), (e.get("text") or "")[:24], flush=True)
            for i in range(3):
                e = wb.receive_json(); print("B<-", e["type"], (e.get("role") or ""), (e.get("text") or "")[:24], flush=True)

    print("MULTI OK", flush=True)
