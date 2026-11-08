# SandboxOps offline audit

This directory is a test report and a re-runnable harness. It does not change application behavior.

The product under test is the isolated checkout. The tested product baseline is `16595487162fac6df3f38247b77bd27075291ccc` on `main`. The documented demo note points at `bea5d337dcab77beac6577533c29ed8ff7b31ea4`. Those SHAs are not a confirmed judging pin. See `AUDIT-REPORT.md`.

## Reproduce

From the repo root, with no `VULTR_INFERENCE_API_KEY` and no Docker required:

```bash
python3 test_agent.py
python3 test_app.py
python3 audit/run_audit.py
```

`test_app.py` listens on `0.0.0.0:18089` for a few seconds. `audit/run_audit.py` serves the same handler on `127.0.0.1` only.

UI probes need the tools used on the runner, installed outside the repo:

```bash
npm install --prefix /tmp/sandboxops-ui-tools --no-fund --no-audit \
  playwright-core@1.56.1 axe-core@4.10.3 lighthouse@12.8.2
```

Chrome was `/usr/bin/google-chrome`. If those tools are missing, the harness records an infra blocker. It does not count that as a pass.

`python3 audit/run_audit.py` exits 0 when the runner finishes writing `audit/results/results.json`. That exit code means the runner completed. It does not mean the product passed. Read `counts` in `results.json`.

The harness does not call Vultr, does not start Docker, and does not contact `http://64.177.13.126/`. Planner responses used in the prompt-execution cases are an in-process stub.
