"""
GSW Alerts — Standalone order notification display
Runs on port 7001. Connects to the inventory Pi via Tailscale SSE stream.
No login, no database — just a fullscreen alert display.
"""

import os
import json
import threading
import time
import queue as _queue
from flask import Flask, render_template, Response, stream_with_context, jsonify

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

# Inventory Pi SSE endpoint (via Tailscale)
INVENTORY_SSE_URL = os.environ.get(
    "INVENTORY_SSE_URL",
    "http://YOUR_INVENTORY_PI_TAILSCALE_IP:7000/api/sse/orders"
)

# Orders API on inventory Pi (to load recent orders on page load)
INVENTORY_ORDERS_URL = os.environ.get(
    "INVENTORY_ORDERS_URL",
    "http://YOUR_INVENTORY_PI_TAILSCALE_IP:7000/api/orders/store"
)

PORT = int(os.environ.get("PORT", 7001))

# ── SSE Bridge ────────────────────────────────────────────────────────────────
# This app connects to the inventory Pi's SSE stream and re-broadcasts
# events to any browser tabs connected to THIS app.
# So the browser never talks directly to the inventory Pi.

_browser_clients: list[_queue.Queue] = []
_bridge_lock = threading.Lock()
_bridge_running = False


def _broadcast(event: str, data: dict):
    """Push event to all connected browser tabs."""
    payload = f"event: {event}\ndata: {json.dumps(data)}\n\n"
    with _bridge_lock:
        dead = []
        for q in _browser_clients:
            try:
                q.put_nowait(payload)
            except _queue.Full:
                dead.append(q)
        for q in dead:
            _browser_clients.remove(q)


def _bridge_loop():
    """Background thread: maintains SSE connection to inventory Pi and rebroadcasts."""
    global _bridge_running
    _bridge_running = True

    while _bridge_running:
        try:
            import urllib.request
            print(f"[Bridge] Connecting to inventory Pi: {INVENTORY_SSE_URL}")

            req = urllib.request.Request(INVENTORY_SSE_URL)
            with urllib.request.urlopen(req, timeout=60) as resp:
                print("[Bridge] Connected to inventory Pi SSE stream")
                buf = ""
                event_name = "message"

                for raw_line in resp:
                    line = raw_line.decode("utf-8").rstrip("\n").rstrip("\r")

                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            data = json.loads(data_str)
                            _broadcast(event_name, data)
                        except json.JSONDecodeError:
                            pass
                        event_name = "message"
                    elif line == "":
                        # blank line = end of event block
                        event_name = "message"
                    # ignore ": ping" keep-alives

        except Exception as e:
            print(f"[Bridge] Connection lost: {e} — retrying in 5s")
            time.sleep(5)


# Start bridge thread at startup
_bridge_thread = threading.Thread(target=_bridge_loop, daemon=True)
_bridge_thread.start()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("alerts.html",
                           inventory_orders_url=INVENTORY_ORDERS_URL)


@app.route("/api/sse")
def sse():
    """SSE endpoint for browser tabs on this alerts app."""
    def stream():
        q: _queue.Queue = _queue.Queue(maxsize=20)
        with _bridge_lock:
            _browser_clients.append(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except _queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _bridge_lock:
                try:
                    _browser_clients.remove(q)
                except ValueError:
                    pass

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/orders")
def recent_orders():
    """Proxy recent orders from inventory Pi so the browser doesn't need direct access."""
    import urllib.request
    try:
        with urllib.request.urlopen(INVENTORY_ORDERS_URL, timeout=5) as r:
            data = json.loads(r.read().decode())
            return jsonify(data[:20])  # latest 20
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/health")
def health():
    return jsonify({"ok": True, "bridge_running": _bridge_running,
                    "connected_tabs": len(_browser_clients)})


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  GSW Alerts running on http://0.0.0.0:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
