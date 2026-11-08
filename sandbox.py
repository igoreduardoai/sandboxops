"""Execution gate.

The default backend is a Linux user/mount/pid/net namespace with a fresh
root made from a read-only Python install. It is not Docker and it is not a
promise of complete arbitrary-code isolation. If that backend cannot be
built, or if the operator asks for Docker and Docker is absent, execution
is refused. The old in-process sandbox is not available.
"""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HELPER = Path(__file__).with_name("jailsetup.py")
TEMPLATE = Path(tempfile.gettempdir()) / "sandboxops-rootfs-v1"
_TEMPLATE_LOCK = threading.Lock()
CODE_LIMIT = 100_000


def docker_command(image="python:3.12-slim"):
    """Argv for the production container path. Constructing it does not run Docker."""
    return [
        "docker", "run", "--rm", "-i", "--network", "none", "--read-only",
        "--tmpfs", "/tmp:size=16m", "--user", "65534:65534", "--cpus", "0.5",
        "--memory", "256m", "--pids-limit", "64", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", image, "python", "-I", "-",
    ]


def configured_backend():
    return os.environ.get("SANDBOX", "namespace")


def execution_mode():
    mode = configured_backend()
    if mode == "docker":
        return "docker" if shutil.which("docker") else "unavailable"
    if mode == "namespace" and sys.platform.startswith("linux"):
        return "namespace"
    return "unavailable"


def _refused(message):
    return {
        "ok": False,
        "executed": False,
        "stdout": "",
        "stderr": message,
        "code": None,
        "backend": "unavailable",
        "error": message,
    }


def _done(ok, stdout, stderr, code, backend, executed=True):
    return {
        "ok": bool(ok),
        "executed": executed,
        "stdout": (stdout or "")[-4000:],
        "stderr": (stderr or "")[-2000:],
        "code": code,
        "backend": backend,
    }


def _copy_libraries(root: Path, binary: Path):
    bins = [binary]
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    dynload = Path(sys.prefix) / "lib" / version / "lib-dynload"
    if dynload.is_dir():
        bins.extend(dynload.glob("*.so"))
    libs = set()
    for item in bins:
        try:
            listing = subprocess.check_output(["ldd", str(item)], text=True, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            continue
        for line in listing.splitlines():
            line = line.strip()
            if "=>" in line:
                parts = line.split()
                if len(parts) >= 3 and parts[2].startswith("/"):
                    libs.add(parts[2])
            elif line.startswith("/") and "ld-linux" in line:
                libs.add(line.split()[0])
    loader = os.path.realpath("/lib64/ld-linux-x86-64.so.2")
    if os.path.exists(loader):
        libs.add(loader)
    for lib in libs:
        dest = root / lib.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(lib, dest)
    if os.path.exists(loader):
        link = root / "lib64" / "ld-linux-x86-64.so.2"
        link.parent.mkdir(parents=True, exist_ok=True)
        if not link.exists():
            link.symlink_to(os.path.relpath(root / loader.lstrip("/"), link.parent))


def ensure_template():
    with _TEMPLATE_LOCK:
        ready = TEMPLATE / "READY"
        if ready.is_file():
            return str(TEMPLATE)
        if TEMPLATE.exists():
            shutil.rmtree(TEMPLATE, ignore_errors=True)
        binary = Path(sys.executable).resolve()
        (TEMPLATE / "usr/bin").mkdir(parents=True)
        shutil.copy2(binary, TEMPLATE / "usr/bin" / "python3")
        _copy_libraries(TEMPLATE, binary)
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        stdlib = Path(sys.prefix) / "lib" / version
        if not stdlib.is_dir():
            raise RuntimeError("python stdlib not found")
        shutil.copytree(
            stdlib,
            TEMPLATE / "usr/lib" / version,
            symlinks=True,
            ignore=shutil.ignore_patterns("__pycache__", "test", "tests"),
        )
        ready.write_text("ok\n", encoding="utf-8")
        return str(TEMPLATE)


def _namespace(code, timeout):
    if not HELPER.is_file():
        return _refused("namespace runtime not available")
    try:
        template = ensure_template()
    except Exception:
        return _refused("namespace runtime not available")
    taskdir = tempfile.mkdtemp(prefix="sandboxops-task-")
    workdir = tempfile.mkdtemp(prefix="sandboxops-work-")
    Path(taskdir, "task.py").write_text(code, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(HELPER), template, taskdir, workdir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            return _done(False, stdout, "timeout", -9, "namespace")
    finally:
        shutil.rmtree(taskdir, ignore_errors=True)
        shutil.rmtree(workdir, ignore_errors=True)
    if proc.returncode == 86 or (stderr or "").startswith("sandbox-setup:"):
        return _refused("namespace setup failed")
    return _done(proc.returncode == 0, stdout, stderr, proc.returncode, "namespace")


def _docker(code, timeout):
    if shutil.which("docker") is None:
        return _refused("docker runtime not available")
    try:
        completed = subprocess.run(
            docker_command(),
            input=code,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
    except subprocess.TimeoutExpired:
        return _done(False, "", "timeout", -9, "docker")
    except OSError:
        return _refused("docker runtime not available")
    return _done(completed.returncode == 0, completed.stdout, completed.stderr, completed.returncode, "docker")


def execute(code: str, timeout=10, dry_run=False):
    if not isinstance(code, str):
        return _refused("code must be a string")
    if len(code) > CODE_LIMIT:
        return _refused("code exceeds limit")
    if dry_run:
        return {"ok": False, "executed": False, "stdout": "", "stderr": "", "code": None, "backend": "dry-run"}
    mode = configured_backend()
    if mode == "docker":
        return _docker(code, timeout)
    if mode == "namespace":
        return _namespace(code, timeout)
    return _refused("local process execution is disabled")
