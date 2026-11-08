#!/usr/bin/env python3
"""HTTP checks. Exits 1 when a check fails. Listens on 127.0.0.1 only."""
import hashlib
import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.pop("SANDBOX", None)
os.environ.pop("VULTR_INFERENCE_API_KEY", None)

import app
import planner

RESULTS = []


def check(name, ok, detail):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ": " + detail)


def call(base, method, path, body=None, raw=None, timeout=20):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    request = urllib.request.Request(base + path, data=data, method=method)
    if data is not None and raw is None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()
    except Exception as err:
        return None, repr(err).encode()


def _channel(value):
    value = value / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _contrast(fg, bg):
    def lum(rgb):
        return 0.2126 * _channel(rgb[0]) + 0.7152 * _channel(rgb[1]) + 0.0722 * _channel(rgb[2])
    light, dark = lum(fg), lum(bg)
    return (max(light, dark) + 0.05) / (min(light, dark) + 0.05)


def digest_ok(record):
    payload = {key: value for key, value in record.items() if key != "sha256"}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return record.get("sha256") == digest


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.H)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        status, raw = call(base, "GET", "/health")
        health = json.loads(raw)
        check(
            "health",
            status == 200 and health.get("planner") == "offline" and health.get("execution") in {"namespace", "unavailable"},
            str(health),
        )
        status, raw = call(base, "GET", "/")
        page = raw.decode()
        contrast = _contrast((255, 255, 255), (10, 47, 107))
        ui_ok = (
            status == 200
            and "SandboxOps" in page
            and 'lang="en"' in page
            and "<main>" in page
            and '<label for="p">' in page
            and 'aria-live="polite"' in page
            and "#0a2f6b" in page
            and contrast >= 4.5
        )
        check("ui_served", ui_ok, f"HTTP {status} bytes={len(raw)} button_contrast={contrast:.2f}")
        status, raw = call(base, "GET", "/favicon.ico")
        check("favicon_no_404", status == 204, f"HTTP {status}")
        status, raw = call(base, "POST", "/api/run", {"task": "bill"}, timeout=30)
        bill = json.loads(raw)
        check(
            "bill_executed_in_backend",
            status == 200 and bill.get("verified") is True and bill["sandbox"]["stdout"].strip() == "551.00" and bill["sandbox"].get("backend") == "namespace" and bill.get("executed") is True and digest_ok(bill),
            f"HTTP {status} verified={bill.get('verified')} backend={bill.get('sandbox', {}).get('backend')} stdout={bill.get('sandbox', {}).get('stdout', '').strip()!r} digest_ok={digest_ok(bill)}",
        )
        status, raw = call(base, "POST", "/api/run", {"task": "bill", "dry_run": True})
        dry = json.loads(raw)
        check(
            "api_dry_run",
            status == 200 and dry.get("executed") is False and dry.get("verified") is False and dry.get("sandbox", {}).get("backend") == "dry-run" and digest_ok(dry),
            f"executed={dry.get('executed')} verified={dry.get('verified')} backend={dry.get('sandbox', {}).get('backend')}",
        )
        status, raw = call(base, "POST", "/api/run", {"task": "network_attempt"}, timeout=20)
        network = json.loads(raw)
        check(
            "network_contained",
            status == 200 and network.get("executed") is True and network.get("contained") is True and network.get("verified") is False and any(token in (network["sandbox"].get("stderr") or "") for token in ("Network is unreachable", "Name or service not known", "Temporary failure in name resolution")),
            f"contained={network.get('contained')} stderr={(network.get('sandbox', {}).get('stderr') or '')[-220:]!r}",
        )
        status, raw = call(base, "POST", "/api/run", {"task": "fork_bomb_ish"}, timeout=20)
        loop = json.loads(raw)
        check(
            "loop_contained",
            status == 200 and loop.get("executed") is True and loop.get("contained") is True and loop.get("verified") is False and loop["sandbox"].get("ok") is False,
            f"contained={loop.get('contained')} code={loop.get('sandbox', {}).get('code')} stderr={(loop.get('sandbox', {}).get('stderr') or '')[:160]!r}",
        )
        status, raw = call(base, "POST", "/api/run", raw=b"{")
        check("bad_json", status == 400, f"HTTP {status} {raw[:80]!r}")
        status, raw = call(base, "POST", "/api/run", {})
        check("missing_task", status == 400, f"HTTP {status}")
        real_plan = planner.plan

        def explode(_task):
            raise RuntimeError("stub-planner-down")

        planner.plan = explode
        try:
            status, raw = call(base, "POST", "/api/run", {"prompt": "hello"})
        finally:
            planner.plan = real_plan
        parsed = json.loads(raw) if raw.startswith(b"{") else {}
        check(
            "planner_error_is_json",
            status == 503 and parsed.get("executed") is False and "error" in parsed,
            f"HTTP {status} body={raw[:180]!r}",
        )
        status, raw = call(base, "GET", "/health")
        check("health_after_planner_error", status == 200 and json.loads(raw).get("status") == "up", raw.decode())
        status, raw = call(base, "POST", "/api/run", {"prompt": "do not execute"})
        offline = json.loads(raw)
        check(
            "offline_prompt_not_executed",
            status == 503 and offline.get("executed") is False and offline.get("code") is None,
            f"HTTP {status} {offline}",
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
