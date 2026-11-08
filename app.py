"""SandboxOps web app (stdlib only). GET / UI, GET /health, GET /api/tasks,
POST /api/run {"task": name} or {"prompt": text} -> plan -> sandbox -> verify -> evidence."""
import json, os, time, hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import agent, planner
import sandbox
from sandbox import execute as sandbox_exec
UI = open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8").read()

def _contained(sandbox_result):
    if not sandbox_result.get("executed") or sandbox_result.get("ok"):
        return False
    stderr = sandbox_result.get("stderr") or ""
    code = sandbox_result.get("code")
    markers = (
        "Network is unreachable", "network disabled", "Name or service not known",
        "Temporary failure in name resolution", "timeout", "MemoryError", "sandbox-signal:",
    )
    return (isinstance(code, int) and code < 0) or any(marker in stderr for marker in markers)

def evidence(rec):
    sb = rec["sandbox"]
    code = sb.get("code")
    if isinstance(code, int) and code < 0 and not sb.get("stderr"):
        sb["stderr"] = f"killed by sandbox limit (signal {-code})"
    rec["executed"] = bool(sb.get("executed"))
    rec["contained"] = _contained(sb)
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = {key: value for key, value in rec.items() if key != "sha256"}
    rec["sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return rec
class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body, default=str)).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {
                "status": "up",
                "backend": sandbox.configured_backend(),
                "execution": sandbox.execution_mode(),
                "planner": "vultr-inference" if planner.llm_available() else "offline",
            })
        if self.path == "/api/tasks":
            return self._send(200, {k: v["goal"] for k, v in agent.TASKS.items()})
        if self.path in ("/", "/index.html"):
            return self._send(200, UI, "text/html; charset=utf-8")
        if self.path == "/favicon.ico":
            return self._send(204, b"")
        self._send(404, {"error": "not found"})
    def do_POST(self):
        if self.path != "/api/run": return self._send(404, {"error": "not found"})
        try: req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except Exception: return self._send(400, {"error": "bad json"})
        try:
            return self._dispatch(req)
        except Exception:
            return self._send(500, {"error": "request failed", "executed": False})
    def _dispatch(self, req):
        dry_run = bool(req.get("dry_run"))
        if req.get("task") in agent.TASKS:
            return self._send(200, evidence(agent.execute(req["task"], dry_run=dry_run)))
        prompt = (req.get("prompt") or "")[:2000]
        if not prompt:
            return self._send(400, {"error": "task or prompt required", "executed": False})
        try:
            planned = planner.plan(prompt)
        except Exception:
            return self._send(503, {"error": "planner failed", "executed": False})
        if planned.get("error") or not planned.get("code"):
            body = {"error": planned.get("error") or "LLM planner offline", "executed": False, **planned}
            return self._send(503, body)
        result = sandbox_exec(planned["code"], 8, dry_run=dry_run)
        verified = None if result.get("executed") else False
        return self._send(200, evidence({
            "task": "prompt", "goal": prompt, "planner": planned["planner"],
            "executed_code": planned["code"], "dry_run": dry_run, "sandbox": result, "verified": verified,
        }))
    def log_message(self, *a): pass
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"SandboxOps on :{port}"); ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
