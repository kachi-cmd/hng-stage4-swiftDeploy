import os
import time
import random
import threading
import json
import math
from http.server import HTTPServer, BaseHTTPRequestHandler

MODE = os.environ.get("MODE", "stable")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "3000"))

START_TIME = time.time()

# ── Chaos state ────────────────────────────────────────────────────────────────
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

# ── Metrics state ──────────────────────────────────────────────────────────────
# Standard Prometheus histogram buckets (seconds)
HISTOGRAM_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

metrics_lock = threading.Lock()

# counters[method][path][status_code] = count
request_counters = {}

# histogram_buckets[le] = count of requests that finished within le seconds
histogram_counts = {str(b): 0 for b in HISTOGRAM_BUCKETS}
histogram_counts["+Inf"] = 0
histogram_sum = 0.0      # sum of all request durations
histogram_total = 0      # total number of requests measured


def record_request(method, path, status_code, duration_seconds):
    """Record one request into counters and histogram."""
    with metrics_lock:
        # Counter
        request_counters \
            .setdefault(method, {}) \
            .setdefault(path, {}) \
            .setdefault(str(status_code), 0)
        request_counters[method][path][str(status_code)] += 1

        # Histogram — increment every bucket the duration falls into
        global histogram_sum, histogram_total
        for b in HISTOGRAM_BUCKETS:
            if duration_seconds <= b:
                histogram_counts[str(b)] += 1
        histogram_counts["+Inf"] += 1
        histogram_sum += duration_seconds
        histogram_total += 1


def build_metrics_output():
    """Render all metrics in Prometheus text format."""
    lines = []

    # ── http_requests_total (counter) ─────────────────────────────────────────
    lines.append("# HELP http_requests_total Total HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    with metrics_lock:
        for method, paths in request_counters.items():
            for path, codes in paths.items():
                for status_code, count in codes.items():
                    lines.append(
                        f'http_requests_total{{method="{method}",'
                        f'path="{path}",status_code="{status_code}"}} {count}'
                    )

    # ── http_request_duration_seconds (histogram) ─────────────────────────────
    lines.append("# HELP http_request_duration_seconds Request duration in seconds")
    lines.append("# TYPE http_request_duration_seconds histogram")
    with metrics_lock:
        for b in HISTOGRAM_BUCKETS:
            lines.append(
                f'http_request_duration_seconds_bucket{{le="{b}"}} '
                f'{histogram_counts[str(b)]}'
            )
        lines.append(
            f'http_request_duration_seconds_bucket{{le="+Inf"}} '
            f'{histogram_counts["+Inf"]}'
        )
        lines.append(f"http_request_duration_seconds_sum {histogram_sum:.6f}")
        lines.append(f"http_request_duration_seconds_count {histogram_total}")

    # ── app_uptime_seconds (gauge) ────────────────────────────────────────────
    lines.append("# HELP app_uptime_seconds Seconds since app started")
    lines.append("# TYPE app_uptime_seconds gauge")
    lines.append(f"app_uptime_seconds {time.time() - START_TIME:.2f}")

    # ── app_mode (gauge: 0=stable, 1=canary) ──────────────────────────────────
    lines.append("# HELP app_mode Current mode (0=stable 1=canary)")
    lines.append("# TYPE app_mode gauge")
    lines.append(f"app_mode {1 if MODE == 'canary' else 0}")

    # ── chaos_active (gauge: 0=none, 1=slow, 2=error) ─────────────────────────
    lines.append("# HELP chaos_active Active chaos mode (0=none 1=slow 2=error)")
    lines.append("# TYPE chaos_active gauge")
    cs = get_chaos()
    if not cs["active"]:
        chaos_val = 0
    elif cs["mode"] == "slow":
        chaos_val = 1
    else:
        chaos_val = 2
    lines.append(f"chaos_active {chaos_val}")

    return "\n".join(lines) + "\n"


# ── Request handler ────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Nginx handles access logs

    def send_json(self, code, data, extra_headers=None):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if MODE == "canary":
            self.send_header("X-Mode", "canary")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def handle_with_metrics(self, handler_fn):
        """Wrap any handler to record timing and status automatically."""
        start = time.time()
        # We need to capture the status code — patch send_response
        self._status_code = 200
        original_send_response = self.send_response
        def patched_send_response(code, message=None):
            self._status_code = code
            original_send_response(code, message)
        self.send_response = patched_send_response

        handler_fn()

        duration = time.time() - start
        record_request(
            self.command,
            self.path.split("?")[0],  # strip query string
            self._status_code,
            duration
        )

    def do_GET(self):
        if self.path == "/metrics":
            # Metrics endpoint — don't record itself to avoid noise
            self.handle_metrics()
        elif self.path == "/":
            self.handle_with_metrics(self.handle_root)
        elif self.path == "/healthz":
            self.handle_with_metrics(self.handle_healthz)
        else:
            self.handle_with_metrics(
                lambda: self.send_json(404, {"error": "not found"})
            )

    def do_POST(self):
        if self.path == "/chaos":
            self.handle_with_metrics(self.handle_chaos)
        else:
            self.handle_with_metrics(
                lambda: self.send_json(404, {"error": "not found"})
            )

    def handle_root(self):
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

    def handle_metrics(self):
        """Serve Prometheus text format metrics."""
        body = build_metrics_output().encode()
        self.send_response(200)
        # Prometheus requires this exact content type
        self.send_header(
            "Content-Type",
            "text/plain; version=0.0.4; charset=utf-8"
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_chaos(self):
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
