#!/usr/bin/env python3
"""Behavioral checks for execution boundaries. Exits 1 when a check fails."""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent
import app
from sandbox import docker_command, execute

RESULTS = []


def check(name, ok, detail):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ": " + detail)


def bill_formula():
    amounts = [620, 95, 40]
    deductible = 500
    total = 0.0
    for amount in amounts:
        applied = min(deductible, amount)
        deductible -= applied
        total += applied + (amount - applied) * 0.2
    return f"{total:.2f}"


def test_docker_argv_is_not_isolation():
    command = docker_command()
    required = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--pids-limit", "64", "--memory", "256m"]
    missing = [flag for flag in required if flag not in command]
    check(
        "docker_argv_construction_not_isolation",
        not missing,
        "Command construction only. Docker was not started and this is not an isolation result. missing=" + str(missing),
    )


def test_bill_gold_is_unchanged():
    expected = "551.00"
    ok = bill_formula() == expected and agent.TASKS["bill"]["check"](expected) and agent.TASKS["bill"]["check"](expected + "\n")
    check(
        "bill_gold_formula",
        ok,
        "Frozen bill check still expects 551.00. This assertion runs in the test process and is not a sandbox claim.",
    )


def test_dry_run_does_not_touch_host():
    marker = Path(tempfile.mktemp(prefix="sandboxops-dry-"))
    marker.write_text("host-secret", encoding="utf-8")
    try:
        result = execute(
            f"open({str(marker)!r}, 'w').write('pwned')\nprint('ran')",
            timeout=8,
            dry_run=True,
        )
        intact = marker.read_text(encoding="utf-8") == "host-secret"
        ok = result.get("executed") is False and result.get("backend") == "dry-run" and intact and "ran" not in (result.get("stdout") or "")
        check("dry_run_does_not_execute", ok, f"result={result} marker_intact={intact}")
    finally:
        marker.unlink(missing_ok=True)


def test_namespace_blocks_host_files_and_loopback():
    marker = Path(tempfile.mktemp(prefix="sandboxops-host-"))
    marker.write_text("host-secret", encoding="utf-8")
    srv = __import__("socket").socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(4)
    port = srv.getsockname()[1]
    got = {}

    def accept():
        try:
            conn, _ = srv.accept()
            got["data"] = conn.recv(32)
            conn.close()
        except Exception as exc:
            got["err"] = type(exc).__name__
        finally:
            srv.close()

    __import__("threading").Thread(target=accept, daemon=True).start()
    previous = os.environ.pop("SANDBOX", None)
    os.environ["SANDBOXOPS_AUDIT_CANARY"] = "canary-not-a-secret"
    code = textwrap.dedent(f"""
        import os, socket, subprocess
        print("canary", os.environ.get("SANDBOXOPS_AUDIT_CANARY"))
        print("passwd", os.path.exists("/etc/passwd"))
        try:
            open({str(marker)!r}, "w").write("pwned")
            print("write_call_returned")
        except Exception as exc:
            print("write_err", type(exc).__name__)
        try:
            s = socket.socket(); s.settimeout(1); s.connect(("127.0.0.1", {port})); s.send(b"sock"); print("sock_ok")
        except Exception as exc:
            print("sock_err", type(exc).__name__)
        try:
            import _socket
            s = _socket.socket(); s.settimeout(1); s.connect(("127.0.0.1", {port})); s.send(b"us"); print("usock_ok")
        except Exception as exc:
            print("usock_err", type(exc).__name__)
        child = subprocess.run(["/usr/bin/python3", "-c", "import socket;s=socket.socket();s.settimeout(1);s.connect(('127.0.0.1',{port}));s.send(b'ch');print('child_ok')"], capture_output=True, text=True, timeout=3)
        print("child_out", child.stdout.strip())
        print("proc_root", os.path.exists("/proc/1/root"))
    """)
    try:
        result = execute(code, timeout=15)
    finally:
        if previous is None:
            os.environ.pop("SANDBOX", None)
        else:
            os.environ["SANDBOX"] = previous
        os.environ.pop("SANDBOXOPS_AUDIT_CANARY", None)
        marker_text = marker.read_text(encoding="utf-8")
        marker.unlink(missing_ok=True)
    stdout = result.get("stdout") or ""
    host_intact = marker_text == "host-secret"
    no_listener = "data" not in got
    ok = (
        result.get("executed") is True
        and result.get("backend") == "namespace"
        and host_intact
        and no_listener
        and "canary None" in stdout
        and "passwd False" in stdout
        and "sock_ok" not in stdout
        and "usock_ok" not in stdout
        and "child_ok" not in stdout
        and "proc_root False" in stdout
    )
    check(
        "namespace_host_boundary",
        ok,
        f"backend={result.get('backend')} executed={result.get('executed')} host_intact={host_intact} listener={got} stdout={stdout!r} stderr={(result.get('stderr') or '')[:240]!r}",
    )


def test_local_backend_refuses():
    previous = os.environ.get("SANDBOX")
    os.environ["SANDBOX"] = "local"
    try:
        result = execute("print('should-not-run')", timeout=8)
    finally:
        if previous is None:
            os.environ.pop("SANDBOX", None)
        else:
            os.environ["SANDBOX"] = previous
    ok = result.get("executed") is False and result.get("backend") == "unavailable" and "should-not-run" not in (result.get("stdout") or "")
    check("local_backend_fail_closed", ok, str(result))


def test_docker_missing_is_structured():
    previous = os.environ.get("SANDBOX")
    os.environ["SANDBOX"] = "docker"
    try:
        if shutil.which("docker"):
            check("docker_missing_is_structured", False, "skipped because docker exists; this environment expectation was no docker binary")
            return
        result = execute("print(1)", timeout=8)
    except Exception as exc:
        result = {"raised": type(exc).__name__}
    finally:
        if previous is None:
            os.environ.pop("SANDBOX", None)
        else:
            os.environ["SANDBOX"] = previous
    ok = result.get("executed") is False and result.get("backend") == "unavailable" and "raised" not in result
    check("docker_missing_is_structured", ok, str(result))


def test_digest_covers_final_record():
    import hashlib
    import json

    record = app.evidence({
        "task": "synthetic",
        "sandbox": {"ok": False, "executed": True, "stdout": "", "stderr": "", "code": -9, "backend": "namespace"},
    })
    payload = {key: value for key, value in record.items() if key != "sha256"}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    ok = record["sha256"] == digest and record["sandbox"]["stderr"] == "killed by sandbox limit (signal 9)" and "contained" in payload
    check("digest_matches_final_record", ok, f"stored={record['sha256']} recomputed={digest} stderr={record['sandbox']['stderr']!r} contained={record.get('contained')}")


def test_limits_and_fork_cap():
    previous = os.environ.pop("SANDBOX", None)
    try:
        memory = execute("try:\n x=bytearray(600*1024*1024)\n print('alloc', len(x))\nexcept MemoryError:\n print('MemoryError')", timeout=15)
        big = execute("try:\n open('/tmp/big.bin','wb').write(b'a'*(11*1024*1024))\n print('wrote-big')\nexcept OSError:\n print('OSError')", timeout=15)
        forks = execute(textwrap.dedent("""
            import os
            import os, time
            pids = []
            try:
                for _ in range(40):
                    pid = os.fork()
                    if pid == 0:
                        time.sleep(30)
                        os._exit(0)
                    pids.append(pid)
                print("spawned", len(pids))
            except OSError as exc:
                print("limited", type(exc).__name__, len(pids))
        """), timeout=15)
    finally:
        if previous is not None:
            os.environ["SANDBOX"] = previous
    mem_out = memory.get("stdout") or ""
    big_out = big.get("stdout") or ""
    fork_out = forks.get("stdout") or ""
    ok = (
        memory.get("backend") == "namespace"
        and "alloc" not in mem_out
        and "wrote-big" not in big_out
        and "spawned" not in fork_out
        and "limited" in fork_out
    )
    check("resource_limits", ok, f"mem={mem_out!r} big={big_out!r} fork={fork_out!r} codes={[memory.get('code'), big.get('code'), forks.get('code')]}")


def main():
    for test in (
        test_docker_argv_is_not_isolation,
        test_bill_gold_is_unchanged,
        test_dry_run_does_not_touch_host,
        test_local_backend_refuses,
        test_docker_missing_is_structured,
        test_digest_covers_final_record,
        test_namespace_blocks_host_files_and_loopback,
        test_limits_and_fork_cap,
    ):
        try:
            test()
        except Exception as exc:
            check(test.__name__, False, f"{type(exc).__name__}: {exc}")
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
