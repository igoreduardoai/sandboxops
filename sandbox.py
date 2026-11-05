"""Containment-first code execution. Locally: a separate process with CPU/memory/file limits,
an empty temp dir, a stripped env, no network (best effort via env + blocked socket import),
and a hard timeout. On Vultr: the same interface, backed by a disposable container/VM."""
import os, resource, subprocess, sys, tempfile, textwrap
PRELUDE = textwrap.dedent("""
    import socket as _s
    def _blocked(*a, **k): raise PermissionError('network disabled in sandbox')
    _s.socket = _blocked; _s.create_connection = _blocked
""")
def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 2**20, 10 * 2**20))
def run(code: str, timeout=10):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "task.py"); open(p, "w").write(PRELUDE + code)
        try:
            r = subprocess.run([sys.executable, "-I", p], cwd=d, capture_output=True, text=True, timeout=timeout,
                               env={"PATH": "/usr/bin:/bin"}, preexec_fn=_limits)
            return {"ok": r.returncode == 0, "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:], "code": r.returncode}
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": "timeout", "code": -9}


def run_docker(code: str, timeout=10, image="python:3.12-slim"):
    """Production backend (Vultr VM/Kubernetes node): throwaway container, no network, read-only
    rootfs, non-root, CPU/mem/pids caps, auto-removed. Select with SANDBOX=docker.
    NOTE: not exercised on the build box (no Docker daemon access); validate on the Vultr instance."""
    cmd = ["docker", "run", "--rm", "-i", "--network", "none", "--read-only", "--tmpfs", "/tmp:size=16m",
           "--user", "65534:65534", "--cpus", "0.5", "--memory", "256m", "--pids-limit", "64",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges", image, "python", "-I", "-"]
    try:
        r = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=timeout + 5)
        return {"ok": r.returncode == 0, "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:], "code": r.returncode, "backend": "docker"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "code": -9, "backend": "docker"}

def execute(code: str, timeout=10):
    return run_docker(code, timeout) if os.getenv("SANDBOX") == "docker" else run(code, timeout)
