"""Loopback-only local visualization and experiment launcher; no official APIs."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import threading
from urllib.parse import urlsplit

from runner import ROOT, run_case

JOB = {"status": "idle"}
LOCK = threading.Lock()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, payload, content_type="application/json; charset=utf-8"):
        data = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/demo":
            path = ROOT / "reports" / "demo_replay.html"
            if path.is_file():
                return self.reply(200, path.read_text(encoding="utf-8"), "text/html; charset=utf-8")
        if self.path == "/":
            return self.reply(200, (ROOT / "web" / "index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        if self.path == "/api/status":
            with LOCK:
                return self.reply(200, dict(JOB))
        if self.path == "/api/runs":
            rows = []
            for path in sorted((ROOT / "runs").glob("*/metrics.json"), reverse=True):
                metrics = load_json(path)
                rows.append({key: metrics.get(key) for key in
                             ("run_id", "seed", "strategy_version", "total_time", "clear_count", "jammer_count", "clear_ratio")})
            return self.reply(200, rows)
        match = re.fullmatch(r"/api/run/([A-Za-z0-9_-]+)", self.path)
        if match:
            path = ROOT / "runs" / match[1] / "result.json"
            if path.is_file():
                return self.reply(200, load_json(path))
        match = re.fullmatch(r"/replay/([A-Za-z0-9_-]+)", self.path)
        if match:
            path = ROOT / "runs" / match[1] / "replay.html"
            if path.is_file():
                return self.reply(200, path.read_text(encoding="utf-8"), "text/html; charset=utf-8")
        return self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/api/start", "/api/export"):
            return self.reply(404, {"error": "not found"})
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            return self.reply(403, {"error": "local origin required"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2048:
                raise ValueError("invalid request size")
            config = json.loads(self.rfile.read(length))
            if self.path == "/api/export":
                if (not isinstance(config, dict) or set(config) - {"run_id", "format"}
                        or config.get("format", "html") not in ("html", "json")
                        or not isinstance(config["run_id"], str)
                        or not re.fullmatch(r"[A-Za-z0-9_-]+", config["run_id"])):
                    raise ValueError("invalid run id")
                directory = ROOT / "runs" / config["run_id"]
                source = directory / "result.json"
                if not source.is_file():
                    return self.reply(404, {"error": "run not found"})
                if config.get("format") == "json":
                    return self.reply(200, {"saved_to": str(source), "open_url": "/api/run/" + config["run_id"]})
                payload = json.dumps(load_json(source), ensure_ascii=False).replace("<", "\\u003c")
                html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
                html = html.replace("const EMBEDDED = null;", "const EMBEDDED = " + payload + ";", 1)
                destination = directory / "replay.html"
                destination.write_text(html, encoding="utf-8")
                return self.reply(200, {"saved_to": str(destination), "open_url": "/replay/" + config["run_id"]})
            allowed = {"seed", "strategy", "scenario", "reception", "error_mode", "count", "depth", "beam_width"}
            if not isinstance(config, dict) or set(config) - allowed:
                raise ValueError("invalid fields")
            if type(config.get("seed")) is not int or not 0 <= config["seed"] <= 2147483647:
                raise ValueError("场景编号应为 0 到 2147483647 的整数")
            if config.get("strategy") not in ("A", "B", "C", "D", "E", "F"):
                raise ValueError("invalid strategy")
            if config.get("depth", 2) not in (1, 2, 3) or not 1 <= config.get("beam_width", 8) <= 32:
                raise ValueError("invalid search settings")
            if config.get("count") is not None and (type(config["count"]) is not int or not 10 <= config["count"] <= 16):
                raise ValueError("invalid source count")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.reply(400, {"error": str(exc)})
        with LOCK:
            if JOB["status"] == "running":
                return self.reply(409, {"error": "已有本地测试正在运行"})
            JOB.clear()
            JOB.update(status="running")
        def work():
            try:
                directory, result = run_case(**config)
                with LOCK:
                    JOB.update(status="done", run_id=directory.name, error=result["metrics"]["client_error"])
            except Exception as exc:
                with LOCK:
                    JOB.update(status="error", error=f"{type(exc).__name__}: {exc}")
        threading.Thread(target=work, daemon=True).start()
        return self.reply(202, {"status": "running"})


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8768)
    args = p.parse_args()
    if args.port == 2026:
        p.error("Port 2026 is reserved for the official simulator and is prohibited here")
    print(f"Local visualization: http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
