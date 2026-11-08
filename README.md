# SandboxOps

An agent that can run code is useful only if a failed or refused run is visible, and if the host files stay out of the run. This candidate does that for one tested backend. It does not claim blast-radius zero, a signed evidence chain, or a competition result.

The earlier public entry is unchanged by this branch. Judging still has no published commit pin, and the rules that were read do not say whether a later push replaces the judged tree. This branch is a repair candidate. It is not merged, not deployed, and not resubmitted.

## The problem this build addresses

On the previous `main` (`16595487162fac6df3f38247b77bd27075291ccc`), the default executor was a child process with a Python socket patch. An audit of that tree showed the child could read and write a host file, open `_socket` to `127.0.0.1`, spawn another Python that did the same, and `fork`. `dry_run` was ignored. A missing `docker` binary raised `FileNotFoundError` instead of a JSON error. The SHA-256 was computed before the final stderr and `contained` fields existed. `test_agent.py` and `test_app.py` printed a count and exited 0 even when a check failed. That audit is preserved at https://github.com/igoreduardoai/sandboxops/pull/1.

## What actually runs

Default `SANDBOX` is `namespace`. `sandbox.py` starts a single-threaded helper that:

1. Enters a new user namespace and maps the calling user to root inside that namespace only.
2. Enters a new network namespace and a new PID namespace.
3. Builds a fresh root from a read-only copy of the Python install, a read-only task file, and a tmpfs at `/tmp`.
4. `pivot_root`s into that root and unmounts the previous root.
5. Sets CPU, address-space, file-size, and process-count limits, then execs `python -I` with `PATH` and `LC_ALL` only.

If setup fails, the helper exits before the task code runs. `SANDBOX=local` is refused. `SANDBOX=docker` runs the Docker argv below only when the `docker` binary exists. If it does not, the API returns a structured refusal and does not fall back to the namespace jail or to a process.

`dry_run: true` returns the action and does not start it.

The SHA-256 on a record is the hash of the final JSON object with the `sha256` field removed, after stderr cleanup and `contained` are set. It is not a signature and it does not prove who ran the code.

## What this environment observed

`python3 repair/run_checks.py` exited 0 after the repair.

| Check | Result |
|---|---|
| `test_agent.py` | 8/8, exit 0 |
| `test_app.py` | 12/12, exit 0 |

Observed on the namespace backend:

- `bill` printed `551.00` and `verified` was true. The frozen check is still `551.00`. A separate formula assertion in the test process also gets `551.00` and is not a sandbox result.
- A host marker file stayed `host-secret`. `/etc/passwd` was absent inside the jail. A parent canary was not in the child environment.
- `socket`, `_socket`, and a child Python failed to reach a listener on the host's `127.0.0.1`. The listener received nothing.
- `/proc/1/root` was absent. Writes to `/usr` inside the jail failed. A write under `/tmp` stayed inside the jail.
- A 600MB allocation raised `MemoryError`. An 11MB write raised `OSError`. Forty simultaneous forks stopped with `BlockingIOError` at 30.
- `network_attempt` ended with `Temporary failure in name resolution` and `contained: true`.
- `fork_bomb_ish` (`while True: pass`) was killed with signal 9 and `contained: true`.
- `dry_run` did not change the host marker.
- `SANDBOX=local` and `SANDBOX=docker` (no binary; `docker` is not installed here) returned `executed: false` and `backend: unavailable`.
- A planner exception returned HTTP 503 JSON. The next `/health` still returned `status: up`.
- Recomputing the response hash with `sha256` removed matched the field, including a record whose stderr was filled in after a negative code.

`docker_command()` includes `--network none`, `--read-only`, `--cap-drop ALL`, `--pids-limit 64`, and `--memory 256m`. That test does not start Docker and is not an isolation result.

## Sponsor path, not re-tested here

The Vultr unit in `deploy/sandboxops.service` still sets `SANDBOX=docker`. That is the production path for the hackathon VM. This repair did not install Docker, did not call `https://api.vultrinference.com`, and did not open `http://64.177.13.126/`. The inference client remains in `planner.py` and returns `inference unavailable` or `LLM planner offline` without executing code. Those live claims from the previous README were not repeated here.

Challenge 1, as published on the event page fetched during the audit, asks for a Vultr VM, a web app, Vultr Serverless Inference, and an isolated sandbox. This branch shows a tested Linux namespace jail and a fail-closed Docker path. It does not show that a judge's Vultr VM is running this commit.

## Behavior this candidate changes

- Unset `SANDBOX` no longer runs a process sandbox. It uses the namespace jail.
- `SANDBOX=local` no longer runs code.
- A missing Docker binary no longer raises an uncaught `FileNotFoundError`.
- `dry_run: true` no longer executes.
- `/health` reports `status: up` plus `execution`. It does not mean a container runtime is available.
- `contained` is false when nothing was executed.
- The digest covers the final record except the digest field itself.
- `test_agent.py` and `test_app.py` exit 1 when a check fails.
- The page no longer says every action is contained or that the blast radius is zero.

## Limits that remain

- The jail shares the host kernel. There is no seccomp filter and no gVisor. The task is root inside its user namespace.
- `open()` of a host path can still create a file in the jail's own filesystem. The host copy of that path was unchanged in the test.
- Forking inside the jail works until the process limit. The test did not claim fork is impossible.
- Docker, Vultr inference, and the public demo host were not exercised.
- The public entry still shows no commit SHA. Whether this branch would be what a judge runs is unknown.
- No score, prize odds, or readiness grade is assigned.

## Run

```bash
python3 test_agent.py
python3 test_app.py
python3 repair/run_checks.py
```

`test_app.py` listens on `127.0.0.1` only. `python3 app.py` still binds `0.0.0.0` so a VM unit can serve the port it is given.

```bash
python3 app.py
```

Open `http://127.0.0.1:8080/`. `bill` should verify `551.00` on the namespace backend. `network_attempt` should show contained. The dry-run checkbox should show that the action was not executed. With `SANDBOX=docker` and no Docker installed, the same buttons should show unavailable.

A task-first walkthrough is in `docs/DEMO.md`. The repair log is `repair/LOOP.md`.

## License

MIT. See `LICENSE`.
