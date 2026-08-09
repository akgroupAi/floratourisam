"""Diagnose live chat delivery against a running server.

Opens two real WebSocket connections as two real users in the same room and
checks whether a message sent by one arrives at the other. This isolates the
backend from the frontend: if this passes, fan-out works and the problem is in
the web client; if it fails, the failure is reported with the reason.

Usage:

    python verify_chat_websocket.py \
        --url https://api.example.com \
        --user-a doctor@example.com --pass-a 'Secret123!' \
        --user-b patient@example.com --pass-b 'Secret123!'

Add --room <uuid> to test one specific room instead of auto-discovering a
shared one. Add --insecure to skip TLS verification.
"""

import argparse
import asyncio
import json
import ssl
import sys
from urllib.parse import urlparse, urlunparse

try:
    import httpx
    import websockets
except ImportError as exc:  # pragma: no cover - operator feedback
    print(f"Missing dependency: {exc}. Run: pip install httpx websockets")
    sys.exit(2)


RECEIVE_TIMEOUT = 10.0


def ok(label, passed, extra=""):
    print(f"{'PASS' if passed else 'FAIL'}  {label}{(' — ' + str(extra)) if extra else ''}")
    return passed


def ws_url(api_base: str, room_id: str, token: str) -> str:
    parts = urlparse(api_base.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    path = f"{parts.path}/api/v1/chat/ws/{room_id}"
    return urlunparse((scheme, parts.netloc, path, "", f"token={token}", ""))


async def login(client: httpx.AsyncClient, base: str, email: str, password: str):
    """Log in on the public portal, falling back to the admin portal."""
    for path in ("/api/v1/auth/login", "/api/v1/auth/admin/login"):
        resp = await client.post(
            f"{base}{path}", json={"email": email, "password": password}
        )
        if resp.status_code == 200:
            body = resp.json()
            return body["tokens"]["access_token"], body["user_id"]
    raise SystemExit(
        f"Login failed for {email}: {resp.status_code} {resp.text[:300]}"
    )


async def find_shared_room(client, base, token_a, token_b):
    """Return a room id both users belong to, or None."""
    async def rooms_for(token):
        resp = await client.get(
            f"{base}/api/v1/chat/rooms", headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        return {r["id"] for r in resp.json().get("rooms", [])}

    shared = (await rooms_for(token_a)) & (await rooms_for(token_b))
    return next(iter(shared), None)


async def create_room(client, base, token_a, user_b_id):
    resp = await client.post(
        f"{base}/api/v1/chat/rooms",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"participant_ids": [user_b_id], "room_type": "consultation"},
    )
    if resp.status_code != 201:
        raise SystemExit(f"Could not create a room: {resp.status_code} {resp.text[:300]}")
    return resp.json()["id"]


async def connect(api_base, room_id, token, label, ssl_ctx):
    url = ws_url(api_base, room_id, token)
    try:
        sock = await websockets.connect(url, ssl=ssl_ctx if url.startswith("wss") else None)
    except Exception as exc:
        print(f"FAIL  {label} could not open the WebSocket — {type(exc).__name__}: {exc}")
        print(f"      URL: {url.split('token=')[0]}token=...")
        print("      A 403/1008 here means the handshake was refused (token or")
        print("      participant check). A timeout or 502 means the proxy is not")
        print("      upgrading the connection — check the nginx WebSocket config.")
        return None

    # The server sends an error frame then closes when it refuses the session.
    try:
        first = await asyncio.wait_for(sock.recv(), timeout=1.0)
        frame = json.loads(first)
        if frame.get("type") == "error":
            print(f"FAIL  {label} was rejected — {frame.get('data', {}).get('message')}")
            await sock.close()
            return None
        print(f"      {label} unexpected first frame: {frame}")
    except asyncio.TimeoutError:
        pass  # Silence is correct: the socket is open and idle
    except Exception:
        pass

    return sock


async def expect_message(sock, needle, label):
    """Wait for a chat message containing needle."""
    deadline = asyncio.get_event_loop().time() + RECEIVE_TIMEOUT
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return ok(label, False, f"nothing arrived within {RECEIVE_TIMEOUT:.0f}s")
        try:
            raw = await asyncio.wait_for(sock.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            return ok(label, False, f"nothing arrived within {RECEIVE_TIMEOUT:.0f}s")
        except Exception as exc:
            return ok(label, False, f"socket closed: {type(exc).__name__}: {exc}")

        try:
            frame = json.loads(raw)
        except ValueError:
            continue

        if frame.get("type") == "error":
            return ok(label, False, f"server error frame: {frame.get('data')}")
        if frame.get("type") == "message":
            content = (frame.get("data") or {}).get("content", "")
            if needle in content:
                return ok(label, True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="API base, e.g. https://api.example.com")
    ap.add_argument("--user-a", required=True)
    ap.add_argument("--pass-a", required=True)
    ap.add_argument("--user-b", required=True)
    ap.add_argument("--pass-b", required=True)
    ap.add_argument("--room", default=None)
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args()

    base = args.url.rstrip("/")
    ssl_ctx = None
    if args.insecure:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    results = []
    async with httpx.AsyncClient(timeout=20.0, verify=not args.insecure) as client:
        token_a, id_a = await login(client, base, args.user_a, args.pass_a)
        token_b, id_b = await login(client, base, args.user_b, args.pass_b)
        results.append(ok("both users logged in", True, f"A={id_a} B={id_b}"))

        room_id = args.room or await find_shared_room(client, base, token_a, token_b)
        if not room_id:
            room_id = await create_room(client, base, token_a, id_b)
            print(f"      created a room for the test: {room_id}")
        results.append(ok("shared room resolved", True, room_id))

        sock_a = await connect(base, room_id, token_a, "user A", ssl_ctx)
        sock_b = await connect(base, room_id, token_b, "user B", ssl_ctx)
        results.append(ok("user A socket open", sock_a is not None))
        results.append(ok("user B socket open", sock_b is not None))

        if not sock_a or not sock_b:
            print("\nBoth sockets must open before delivery can be tested.")
            return 1

        # --- 1. WebSocket send -> the other side receives -------------------
        needle = f"ws-probe-{id_a[:8]}"
        await sock_a.send(json.dumps({"type": "message", "data": {"content": needle}}))
        results.append(await expect_message(sock_b, needle, "B receives A's WebSocket message"))
        results.append(await expect_message(sock_a, needle, "A receives its own echo"))

        # --- 2. REST send -> WebSocket receives -----------------------------
        needle2 = f"rest-probe-{id_b[:8]}"
        resp = await client.post(
            f"{base}/api/v1/chat/rooms/{room_id}/messages",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"room_id": room_id, "content": needle2, "message_type": "text"},
        )
        results.append(ok("REST send accepted", resp.status_code == 201, resp.status_code))
        if resp.status_code == 201:
            results.append(await expect_message(sock_a, needle2, "A receives the REST message live"))

        await sock_a.close()
        await sock_b.close()

    print(f"\n{sum(results)}/{len(results)} passed")
    if all(results):
        print("\nBackend fan-out is working. The problem is in the web client —\n"
              "check that it opens the socket and renders incoming 'message' frames.")
    else:
        print("\nBackend fan-out is NOT working. Fix the first FAIL above.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
