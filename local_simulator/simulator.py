"""One entry point for the independent Q3 simulator (Python standard library)."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["gui", "run", "compare", "test"], nargs="?", default="gui")
    args, remaining = parser.parse_known_args()
    if args.command == "run":
        return subprocess.call([sys.executable, str(ROOT / "code" / "runner.py"), *remaining], cwd=ROOT)
    if args.command == "compare":
        return subprocess.call([sys.executable, str(ROOT / "code" / "benchmark.py")], cwd=ROOT)
    if args.command == "test":
        return subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
    url = "http://127.0.0.1:8768"
    def available():
        try:
            with urllib.request.urlopen(url + "/api/status", timeout=.5) as response:
                return json.loads(response.read()).get("status") in ("idle", "running", "done", "error")
        except (OSError, ValueError):
            return False
    if not available():
        logs = (ROOT / "server.launch.log").open("a", encoding="utf-8")
        subprocess.Popen([sys.executable, str(ROOT / "code" / "server.py")], cwd=ROOT,
                         stdout=logs, stderr=logs,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        logs.close()
        for _ in range(30):
            if available():
                break
            time.sleep(.1)
        else:
            raise RuntimeError("Local server did not start; see server.launch.log")
    webbrowser.open(url)
    print(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
