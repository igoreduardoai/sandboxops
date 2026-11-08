# Repair loop

Maximum rounds: 3. Stop on no improvement, a repeated failure, or an unsafe shortcut. This log is the implementer's record of commands and outputs. It is not an independent judge, and the two test files are not two judges. They check different surfaces of the same behavior.

Product baseline: `16595487162fac6df3f38247b77bd27075291ccc`. Audit evidence stays on https://github.com/igoreduardoai/sandboxops/pull/1 (`7c114ac30e47f83aa72bd4be7ecfb1817338aac4`). This branch does not edit that PR.

Started 2026-11-08 13:37 CST. Event `endAt` observed earlier was 2026-11-08 17:00 CST. No merge, deploy, portal edit, or resubmit.

## Round 1 — reproduce

Allowlisted commands against the baseline product, with the new checks already written:

| Command | Exit |
|---|---|
| `python3 test_agent.py` | 1 |
| `python3 test_app.py` | 1 |

`repair/evidence/before-test_agent.txt` stops at `TypeError: execute() got an unexpected keyword argument 'dry_run'`. The bill formula check had passed before that crash. `before-test_app.txt` shows `/health` still reporting `backend: local`, `bill` verified on a backend of `None` with `digest_ok=False`, dry run still verified, the planner exception closing the connection, and the offline prompt body missing `executed: false`.

Evidence review for the repair, not a second model: the audit already showed host file, `_socket`, subprocess, and fork escapes. Patching more names in the prelude would repeat that failure. A read-only pivot-root jail is a smaller claim that can be tested. If it cannot be built, refusal is the result. Docker argv must stay labeled as construction. The digest has to be computed after the final fields. Tests have to exit non-zero.

## Round 2 — repair and retest

`sandbox.py` no longer runs the process sandbox. `jailsetup.py` performs the namespace setup. The first helper used the `unshare` binary and lost CPU-limit deaths (`sigprocmask unblock failed`, exit 1, `contained` false). The helper now maps the host uid captured before `unshare` and reports `sandbox-signal`. An earlier id-map attempt used the overflow uid 65534 and failed with `sandbox-setup: id map 1`.

After that fix, before the UI edit:

| Command | Exit | Count |
|---|---|---|
| `python3 test_agent.py` | 0 | 7/7 |
| `python3 test_app.py` | 0 | 11/11 |

`bill` verified `551.00` inside the namespace backend. Host marker, loopback, canary, `/etc/passwd`, memory, file size, and the fork cap behaved as recorded in the final README.

## Round 3 — thesis, UI, retest

The page lost the "Blast Radius Zero" and "every action runs contained" lines. It gained `lang`, `main`, a label, `aria-live`, a dry-run checkbox, and button color `#0a2f6b` (white contrast 12.87:1). `/favicon.ico` returns 204. README and `docs/DEMO.md` match the tests.

Final allowlisted run:

| Command | Exit | Count |
|---|---|---|
| `python3 test_agent.py` | 0 | 8/8 |
| `python3 test_app.py` | 0 | 12/12 |
| `python3 repair/run_checks.py` | 0 | 0/2 commands failed |

Saved as `repair/evidence/after-test_agent.txt` and `after-test_app.txt`.

## Before / after

| Issue | Before | After |
|---|---|---|
| Host file read/write, `_socket`, subprocess loopback | Allowed by the process sandbox (audit PR 1) | Host marker unchanged; listener received nothing; `/etc/passwd` absent in the jail |
| `fork` | Host `fork` returned | In-jail fork stopped at 30 with `BlockingIOError`; not a claim that fork is impossible |
| `dry_run` | Unexpected keyword; API still verified `bill` | `executed: false`, host marker unchanged |
| Docker absent | Uncaught `FileNotFoundError` | `backend: unavailable`, `executed: false` |
| Digest | Final object did not match | Recomputed hash matches, including rewritten stderr |
| Tests | Exit 0 with no failure status | Exit 1 on failure; this run exited 0 because the checks passed |
| Planner exception | Connection dropped | HTTP 503 JSON; `/health` still up |
| UI a11y | Missing `lang`, label, main, live region; button contrast 4.499 | Those are present; contrast 12.87. Live axe was not re-run |
| Docker isolation | Not run | Still not run. Argv test is labeled construction only |
| Live Vultr inference and public VM | Not run in the audit | Still not run |

No fourth round. The remaining gaps are limits of the tested jail and unverified sponsor services, not a repeated test failure.
