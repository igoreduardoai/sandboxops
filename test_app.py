import json, os, subprocess, sys, time, urllib.request
port = "18089"; p = subprocess.Popen([sys.executable, "app.py"], env={**os.environ, "PORT": port})
try:
    time.sleep(1.5); u = f"http://127.0.0.1:{port}"
    h = json.load(urllib.request.urlopen(u + "/health"))
    def run(t): return json.load(urllib.request.urlopen(urllib.request.Request(u + "/api/run", json.dumps({"task": t}).encode(), {"Content-Type": "application/json"})))
    R = [h["status"] == "ok", run("bill")["verified"] is True, run("network_attempt")["contained"] is True, run("fork_bomb_ish")["contained"] is True,
         b"SandboxOps" in urllib.request.urlopen(u + "/").read()]
    print(R, f"{sum(R)}/{len(R)} passed")
finally: p.terminate()
