"""Planner: turns a natural-language task into Python code.
Uses Vultr Serverless Inference (OpenAI-compatible, https://api.vultrinference.com/v1) when
VULTR_INFERENCE_API_KEY is set; otherwise falls back to the deterministic demo planner."""
import json, os, re, urllib.request
BASE = os.getenv("VULTR_INFERENCE_BASE", "https://api.vultrinference.com/v1")
MODEL = os.getenv("VULTR_INFERENCE_MODEL", "glm-5.3")
SYSTEM = ("You write a single self-contained Python 3 script that solves the user's task and prints only the "
          "final answer. Standard library only. No network, no file writes outside /tmp. Reply with code only.")
def llm_available():
    return bool(os.getenv("VULTR_INFERENCE_API_KEY"))
def plan(task: str) -> dict:
    if not llm_available():
        return {"planner": "offline", "code": None, "error": "LLM planner offline", "note": "VULTR_INFERENCE_API_KEY not set"}
    body = json.dumps({"model": MODEL, "messages": [{"role": "system", "content": SYSTEM},
                       {"role": "user", "content": task}], "temperature": 0}).encode()
    req = urllib.request.Request(BASE + "/chat/completions", data=body, headers={
        "Authorization": "Bearer " + os.environ["VULTR_INFERENCE_API_KEY"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            txt = json.load(response)["choices"][0]["message"]["content"]
    except Exception:
        return {"planner": f"vultr-inference:{MODEL}", "code": None, "error": "inference unavailable"}
    match = re.search(r"```(?:python)?\n(.*?)```", txt, re.S)
    return {"planner": f"vultr-inference:{MODEL}", "code": (match.group(1) if match else txt).strip()}
