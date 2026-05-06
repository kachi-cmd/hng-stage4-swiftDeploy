import os
import time
import random
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

MODE = os.environ.get("MODE", "stable")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "3000"))

START_TIME = time.time()

# Chaos state — shared across all requests, protected by a lock
chaos_state = {
    "mode": None,
    "duration": 0,
    "rate": 0.0,
    "active": False,
    "lock": threading.Lock()
}


def get_chaos():
    with chaos_state["lock"]:
        return dict(chaos_state)


def set_chaos(mode=None, duration=0, rate=0.0, active=False):
    with chaos_state["lock"]:
        chaos_state["mode"] = mode
        chaos_state["duration"] = duration
        chaos_state["rate"] = rate
        chaos_state["active"] = active


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suppress default stdout logging — Nginx handles access logs
        pass

    def send_json(self, code, data, extra_headers=None):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # Canary mode stamps every response with this header
        if MODE == "canary":
            self.send_header("X-Mode", "canary")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.handle_root()
        elif self.path == "/healthz":
            self.handle_healthz()
        else:
            self.send_json(404, {"error": "not found", "path": self.path})

    def do_POST(self):
        if self.path == "/chaos":
            self.handle_chaos()
        else:
            self.send_json(404, {"error": "not found", "path": self.path})

    def handle_root(self):
        # Apply any active chaos before responding
        cs = get_chaos()
        if cs["active"]:
            if cs["mode"] == "slow":
                time.sleep(cs["duration"])
            elif cs["mode"] == "error":
                if random.random() < cs["rate"]:
                    self.send_json(500, {
                        "error": "chaos-induced error",
                        "mode": "error"
                    })
                    return

        self.send_json(200, {
            "message": f"Welcome! Running in {MODE} mode",
            "mode": MODE,
            "version": APP_VERSION,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        })

    def handle_healthz(self):
        uptime = round(time.time() - START_TIME, 2)
        self.send_json(200, {
            "status": "ok",
            "uptime_seconds": uptime,
            "mode": MODE,
            "version": APP_VERSION
        })

    def handle_chaos(self):
        # Chaos endpoint is canary-only — stable mode gets a 403
        if MODE != "canary":
            self.send_json(403, {
                "error": "chaos endpoint only available in canary mode",
                "current_mode": MODE
            })
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
        except Exception:
            self.send_json(400, {"error": "invalid JSON body"})
            return

        mode = data.get("mode")
        if mode == "slow":
            duration = data.get("duration", 1)
            set_chaos(mode="slow", duration=duration, active=True)
            self.send_json(200, {
                "status": "chaos activated",
                "mode": "slow",
                "duration": duration
            })
        elif mode == "error":
            rate = data.get("rate", 0.5)
            set_chaos(mode="error", rate=rate, active=True)
            self.send_json(200, {
                "status": "chaos activated",
                "mode": "error",
                "rate": rate
            })
        elif mode == "recover":
            set_chaos(active=False)
            self.send_json(200, {"status": "chaos deactivated"})
        else:
            self.send_json(400, {
                "error": f"unknown chaos mode: {mode}",
                "valid_modes": ["slow", "error", "recover"]
            })


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", APP_PORT), Handler)
    print(
        f"[swiftdeploy] starting on port {APP_PORT} "
        f"| mode={MODE} | version={APP_VERSION}",
        flush=True
    )
    server.serve_forever()
