"""SandboxOps web app (stdlib only). GET / UI, GET /health, GET /api/tasks,
POST /api/run {"task": name} or {"prompt": text} -> plan -> sandbox -> verify -> evidence."""
import json, os, time, hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import agent, planner
from sandbox import execute as sandbox_exec
UI = open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8").read()
def evidence(rec):
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec["sha256"] = hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()
    sb = rec["sandbox"]
    if sb.get("code", 0) < 0 and not sb["stderr"]: sb["stderr"] = f"killed by sandbox limit (signal {-sb['code']})"
    rec["contained"] = (not sb["ok"]) and (sb.get("code", 0) < 0 or any(k in (sb.get("stderr") or "") for k in ("network disabled", "timeout", "PermissionError", "MemoryError", "gaierror", "name resolution", "Network is unreachable", "Name or service not known")))
    return rec
class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body, default=str)).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok", "backend": os.getenv("SANDBOX", "local"), "planner": "vultr-inference" if planner.llm_available() else "offline"})
        if self.path == "/api/tasks":
            return self._send(200, {k: v["goal"] for k, v in agent.TASKS.items()})
        if self.path in ("/", "/index.html"):
            return self._send(200, UI, "text/html; charset=utf-8")
        self._send(404, {"error": "not found"})
    def do_POST(self):
        if self.path != "/api/run": return self._send(404, {"error": "not found"})
        try: req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except Exception: return self._send(400, {"error": "bad json"})
        if req.get("task") in agent.TASKS:
            return self._send(200, evidence(agent.execute(req["task"])))
        prompt = (req.get("prompt") or "")[:2000]
        if not prompt: return self._send(400, {"error": "task or prompt required"})
        p = planner.plan(prompt)
        if not p["code"]: return self._send(503, {"error": "LLM planner offline", **p})
        r = sandbox_exec(p["code"], 8)
        return self._send(200, evidence({"task": "prompt", "goal": prompt, "planner": p["planner"], "executed_code": p["code"], "sandbox": r, "verified": None}))
    def log_message(self, *a): pass
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    print(f"SandboxOps on :{port}"); ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
