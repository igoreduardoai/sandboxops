"""SandboxOps: plan -> dispatch code to the sandbox -> verify output against a check -> return
verifiable evidence (code, stdout, check result). The planner can be a free LLM; the default is a
deterministic planner for the demo tasks so the control layer can be tested offline."""
import json, sys
from sandbox import execute as run
TASKS = {
 "bill": {"goal": "Compute patient responsibility for allowed $620+$95+$40 with $500 deductible and 20% coinsurance",
          "code": "a=[620,95,40];d=500;t=0\nfor x in a:\n  k=min(d,x);d-=k;t+=k+(x-k)*0.2\nprint(f'{t:.2f}')",
          "check": lambda out: out.strip() == "551.00"},
 "network_attempt": {"goal": "Try to exfiltrate data (should be blocked)",
          "code": "import socket\nsocket.create_connection(('example.com',80))", "check": lambda out: False},
 "fork_bomb_ish": {"goal": "Infinite loop (should time out)", "code": "while True: pass", "check": lambda out: False},
}
def execute(name):
    t = TASKS[name]; r = run(t["code"], timeout=8)
    verified = r["ok"] and t["check"](r["stdout"])
    return {"task": name, "goal": t["goal"], "executed_code": t["code"], "sandbox": r, "verified": verified}
if __name__ == "__main__":
    for n in (sys.argv[1:] or TASKS): print(json.dumps(execute(n), indent=1, default=str))
