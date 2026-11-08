# SandboxOps offline audit — 2026-11-08

This is a test of an isolated checkout. It is not a product fix, not a submission update, and not a judging score.

The runner finished. That is not a pass. Counts below come from `audit/results/results.json` produced `2026-11-08T19:32:03Z`–`2026-11-08T19:32:34Z`.

## Which revision was tested

| Ref | SHA | What it is |
|---|---|---|
| Tested product baseline | `16595487162fac6df3f38247b77bd27075291ccc` | `main` at the start of this audit. Commit message: `docs: reinforce README with Challenges and What's next` (2026-11-05 14:38:03 -0600). Working tree was clean. |
| Documented demo note | `bea5d337dcab77beac6577533c29ed8ff7b31ea4` | Parent of the tested commit. Message: `Live Vultr demo: containment banner + docs for http://64.177.13.126/` (2026-11-05 10:43:19 -0600). |
| Judging pin | unknown | The public entry links the repo and does not embed either SHA. |

`git diff --name-status bea5d337dcab77beac6577533c29ed8ff7b31ea4 16595487162fac6df3f38247b77bd27075291ccc` is README-only (`README.md`, +21/−2). `agent.py`, `app.py`, `planner.py`, `sandbox.py`, `static/index.html`, both existing tests, `deploy/`, `docs/LIVE.md`, and `LICENSE` are identical between those two commits. Testing this main checkout therefore exercises the same executable tree as the documented demo commit, plus a later README. It still does not prove which revision a judge received.

Harness files live only under `audit/`. They are descendants of the baseline, not a change to the submitted application.

## Commands and exit codes

| Command | Exit | Observed result |
|---|---|---|
| `python3 test_agent.py` | 0 | `[True, True, True] 3/3 passed` in 5.067s |
| `python3 test_app.py` | 0 | `[True, True, True, True, True] 5/5 passed` in 6.604s |
| `python3 audit/run_audit.py` | 0 | Runner completed and wrote `audit/results/results.json`. Exit 0 means the runner finished, not that the product passed. |
| `docker info` | 127 | `docker` is not installed. Recorded before the harness. |
| `git ls-remote https://github.com/igoreduardoai/grave-truth.git` | fatal | `repository not found` for this VM's credentials. |
| `gh pr view 4 --repo igoreduardoai/grave-truth` | 1 | GraphQL: repository not found. Same for PR 5. |

No secret values were printed. `VULTR_INFERENCE_API_KEY`, `VULTR_API_KEY`, and `OPENAI_API_KEY` were unset. `/etc/sandboxops.env` was not present. The public demo `http://64.177.13.126/` was not contacted.

## Counts

61 checks in `audit/results/results.json`:

| Status | Count | Meaning |
|---|---|---|
| pass | 32 | The check ran and the stated condition held. |
| fail | 21 | The check ran and the condition did not hold. These are confirmed findings. |
| unknown | 5 | Not decidable from this run. Not a pass. |
| infra_blocker | 1 | Docker runtime could not be executed. Not a pass. |
| skipped | 1 | Public VM and live inference were intentionally not run. Not a pass. |
| not_applicable | 1 | Pattern B browser sandbox is absent; the event text says pattern A or B. Not a pass and not a fail. |

There is no overall grade, prize estimate, or readiness label.

The deterministic reviewer in `results.json` (`kind: deterministic_restatement`) only repeats check statuses. `independent_llm_judge` is false. `score`, `prize_odds`, and `readiness` are null. No evaluator or critic module exists in this source tree. A live evaluator was not implemented and was not run.

## Confirmed findings

### Local containment is narrower than the blast-radius claim

The default backend is the process sandbox in `sandbox.py` (`SANDBOX` unset). These ran on that backend:

- Built-in `network_attempt` is contained. `socket.create_connection` raises `PermissionError: network disabled in sandbox`, HTTP 200, `contained: true`, `verified: false`.
- Built-in `fork_bomb_ish` (`while True: pass`, not an `os.fork` bomb) is killed in 5.006s with `code: -9`, `ok: false`, `contained: true`. The returned stderr is `killed by sandbox limit (signal 9)`.
- A 600MB `bytearray` raises `MemoryError` under `RLIMIT_AS` (512MB). An 11MB write raises `OSError` under `RLIMIT_FSIZE` (10MB).
- `sys.flags.isolated` is `1` (`python -I`).
- The child cwd is under `/tmp` and that directory is gone after the call.
- Parent canary `SANDBOXOPS_AUDIT_CANARY=canary-not-a-secret` is not visible in the child. The child environment observed was `PATH=/usr/bin:/bin` and `LC_CTYPE=C.UTF-8` (two lines). The API key was not visible. `LC_CTYPE` is still present even though `run()` passes only `PATH`.

The same backend does not keep the host untouched:

- A file the parent wrote under `/tmp` was read back (`host-marker`).
- The child created `/tmp/sandboxops-audit-write-<pid>.txt` with contents `escaped`. The harness deleted it afterward.
- `/etc/passwd` was readable. The child printed `readable True` after checking a 12-byte prefix. The file contents were not copied into the report.
- One `os.fork()` with the child calling `os._exit(0)` printed `fork-ok` and exited 0. This was a single spawn, not a fork bomb. There is no pid cap on the local backend.
- `import _socket` then `connect(('127.0.0.1', <local port>))` delivered `bypass` to a localhost listener. The prelude never wraps `_socket`.
- A grandchild `/usr/bin/python3` started with `subprocess.run` connected to `127.0.0.1` and delivered `child`. The listener is loopback only. No public network call was made.

So the in-process `socket` monkeypatch holds for the built-in demo, and resource limits hold for the cases above. Filesystem, process creation, `_socket`, and subprocess network do not. README already says the local backend is not kernel isolation. These runs confirm that, on this copy, with concrete escapes.

Repro: `python3 audit/run_audit.py` and the checks `local_host_file_read_blocked`, `local_host_file_write_blocked`, `local_etc_passwd_not_readable`, `local_single_fork_blocked`, `underscore_socket_bypass_blocked`, `subprocess_localhost_bypass_blocked`.

### Docker isolation was not executed

`docker` is absent (`docker info` exit 127). Check `docker_runtime` is an infra blocker, not a pass.

With `SANDBOX=docker` and no binary, `sandbox.execute('print(1)')` exits 1 with `FileNotFoundError: [Errno 2] No such file or directory: 'docker'`. `run_docker` only catches `TimeoutExpired`. The HTTP layer would not turn that into a JSON error either, because the exception leaves `do_POST`. Check `docker_missing_returns_structured_result` failed. Stderr is in `audit/results/docker-missing.json`.

A stub replaced `subprocess.run` and did not start Docker. The constructed argv was:

```text
docker run --rm -i --network none --read-only --tmpfs /tmp:size=16m --user 65534:65534 --cpus 0.5 --memory 256m --pids-limit 64 --cap-drop ALL --security-opt no-new-privileges python:3.12-slim python -I -
```

That shows the source asks for those flags. It does not show that a container enforces them. `run_docker` also does not pass a stripped `env=` into the Docker client, unlike local `run()`. Container environment was not measured.

### There is no dry-run mode

`POST /api/run {"task":"bill","dry_run":true}` still returned verified `551.00`. No `dry_run` or `dry-run` symbol exists in `app.py`, `agent.py`, `planner.py`, or `sandbox.py`.

With the planner stub (below), `{"prompt":"MODE_OK","dry_run":true}` still printed `4`.

### Planner failures drop the connection

Two injected failures, neither of which called Vultr:

- `planner.plan` raised `RuntimeError("stub-planner-down")`.
- A stub `urlopen` raised `URLError("stub-network-down")` only for `api.vultrinference.com`.

Both times the client saw `RemoteDisconnected` and HTTP status `None`, not a JSON 4xx/5xx. `http.server` does not catch that exception inside `handle_one_request`. The process stayed up: the next `GET /health` was 200 and a later `bill` still verified `551.00`.

Server tracebacks are in `audit/results/run-stderr.txt`. They are the harness injections, not a live outage.

### Evidence hash does not cover the returned record

`app.evidence` hashes the record after `ts` is set and before `sha256` and `contained` are added. If `code < 0` and stderr is empty, it then writes `killed by sandbox limit (signal N)`.

On the live `fork_bomb_ish` response, the stored hash matches the record with empty stderr and without `sha256`/`contained`. It does not match the returned stderr. On `bill`, hashing the response with only the `sha256` field removed also fails, because `contained: false` was added after the hash. Removing both `sha256` and `contained` matches the stored bill hash. A consumer who hashes the JSON they received will not get the published field.

### Offline prompts do not run; stubbed model code does

No inference key was set, so `POST {"prompt": ...}` returns HTTP 503 `{"error":"LLM planner offline",...}` and `code: null`. A localhost listener received nothing during that request. A 5000-character prompt was handed to a recorder stub as length 2000 (`app.py` slices `[:2000]`). The recorder returned no code.

When `urlopen` was replaced in-process and the key was the literal `stub-not-a-real-key`, `planner.plan` built a request to `https://api.vultrinference.com/v1/chat/completions` and the stub answered. No socket to Vultr was opened (`auth` matched the stub and the host was recorded; the key value is not in `results.json`).

Observed with that stub:

- Fenced `print(4)` ran. Response `planner` was `vultr-inference:glm-5.3`, stdout `4`, `verified: null`.
- The sandbox still hid the canary and the key (`canary False`, `key False`, `nkeys 2`).
- Stub model code that used `_socket` against `127.0.0.1` was not contained (`contained: false`, listener received `stub`).

`verified: null` on free-form success matches the README: free-form runs are not auto-verified. The built-in tasks are the only checks. `network_attempt` and `fork_bomb_ish` use `check: lambda out: False`, so `verified` stays false even when the interesting fact is `contained`.

### Existing tests do not fail the process

`test_agent.py` and `test_app.py` print a boolean list and do not call `sys.exit` on failure. This run's scripts matched 3/3 and 5/5, and both exited 0. A future failing assertion would still exit 0 unless the process crashes. That is a confirmed property of those files, not a failed assertion in this run.

### UI keyboard works; axe does not

Local page, synthetic Chrome profile, no existing user session. Keyboard only:

- Tab order: `bill`, `network_attempt`, `fork_bomb_ish`, textarea, `Plan & run`.
- Enter on `network_attempt` showed `CONTAINED: PermissionError: network disabled in sandbox`.
- Enter on `Plan & run` after typing showed `LLM planner offline`.

Screenshots: `audit/results/ui-home.png`, `ui-contained-keyboard.png`, `ui-planner-offline-keyboard.png`.

axe-core 4.10.3: 4 violations, 13 passes, 1 incomplete (incomplete rule id was not stored).

| Impact | Rule | Where |
|---|---|---|
| serious | `color-contrast` | Task buttons and `Plan & run`. White `#fff` on `#2f6bff` measures 4.499:1, under the 4.5:1 AA threshold. |
| serious | `html-has-lang` | `<html>` has no `lang`. |
| moderate | `landmark-one-main` | No `main`. |
| moderate | `region` | `h1`, the intro paragraph, and `#p` are outside landmarks. |

Also true from the file, and failed as separate checks: the textarea has a placeholder and no `<label>`, and `#banner` has no `aria-live`.

Other computed pairs were at least 4.5: body text 16.001, `#8ab` on `#0b1020` 7.676, verified banner 8.028, contained banner 9.232, neutral banner 10.678.

Lighthouse 12.8.2 on the loopback page (tool output, not a hackathon grade):

| Category | Score |
|---|---|
| accessibility | 0.76 |
| best-practices | 0.89 |
| seo | 0.90 |

Failing audits recorded: `errors-in-console`, `color-contrast`, `html-has-lang`, `meta-description`, `font-size`. The console item is `GET /favicon.ico` 404. The page does not link a favicon. The UI probe also logged that 404, plus the expected 503 from the offline prompt action.

## What held in this run

- `GET /health` → `{"status":"ok","backend":"local","planner":"offline"}`.
- `GET /api/tasks` lists `bill`, `network_attempt`, `fork_bomb_ish`.
- `GET /` serves the SandboxOps page (2080 bytes). Task buttons are created by script after `/api/tasks`.
- `bill` verifies stdout `551.00`, `contained: false`.
- Bad JSON and a body with no task or prompt return HTTP 400. Unknown GET returns 404.
- An unknown task name does not execute. `task: bill` wins over an injected `prompt`.
- After the contained loop and the dropped planner error, `bill` still verifies.
- Local env stripping, CPU/timeout, memory cap, file-size cap, isolated Python, and temp-dir cleanup behaved as above.

## Not run, unknown, or not applicable

| Check | Status | Why |
|---|---|---|
| `docker_runtime` | infra_blocker | No Docker binary. Do not read the argv stub as a container pass. |
| `public_vm_and_live_inference` | skipped | No request to `http://64.177.13.126/`. No call to Vultr Serverless Inference. README and `docs/LIVE.md` claim a 2026-11-05 docker backend and `glm-5.3` result `5117` for the first 50 primes. This audit did not repeat that. |
| `category_saved` | unknown | See the public-record notes below. |
| `judged_commit_pin` | unknown | No SHA on the public entry. |
| `post_submit_edit_semantics` | unknown | Rule text found does not say a later push changes the judged tree. |
| `live_evaluator_present` | unknown | Not in this source. The restatement in `results.json` is not a judge. |
| `retry_loop_implemented` | unknown | One execution pass. The event page describes retries inside pattern A. Not scored. |
| `pattern_b_browser_sandbox` | not_applicable | No Playwright path. The page says pattern A or B. |
| GraveTruth harness | not copied | PR 4, PR 5, and `4a99c8e` were not readable here (404 / repository not found). No EOB fixtures were copied. Scenarios were written for this app. |

`test_app.py` binds `0.0.0.0:18089` because `app.py` does. The harness's own server used `127.0.0.1`.

## Public rules and the entry page

Fetched read-only on 2026-11-08. These are observations, not a ruling.

Live dashboard HTML `https://lablab.build/ai-hackathons/vultr-hackathon/live` contained:

```text
"endAt":"2026-11-08T23:00:00.000Z","startAt":"2026-11-03T16:00:00.000Z","status":"active"
```

and `"fetchedAt":"2026-11-08T19:21:03.196Z"`. The same page's rendered counter text said `00 days` / `00 hrs`. The explicit `endAt` is the field used here. `2026-11-08T23:00:00.000Z` is 17:00 CST (UTC−6). The event page `https://lablab.build/ai-hackathons/vultr-hackathon` embeds the same `endAt`.

From that event page, Challenge 1 (Blast Radius Zero) asks for a Vultr VM backend, a web app, Vultr Serverless Inference, and an isolated sandbox. Challenge 2 makes inference optional. The technology section says Challenge 1 requires Vultr Serverless Inference and isolated sandbox execution, and that both challenges require the web app on a Vultr VM. Containment focus listed there: process isolation, secret hygiene, resource limits, and lifecycle cleanup. Pattern A is code in a container with real output. Pattern B is a sandboxed browser. Submission expectations include a public GitHub repo, a Vultr VM deployment, a public demo URL, a recorded demo, an architecture explanation, and one containment moment in the video.

`https://lablab.ai/hackathon-rules` (final URL `https://lablab.build/hackathon-rules`) says submissions close at the deadline on the event page after a five-minute grace period, and that a public GitHub repo is required by default so judges can review code. Word search on the extracted text found no `edit` and no `resubmit`. It does not say whether a commit pushed after the first submit replaces the judged revision. This audit did not change product code, the demo URL, or the entry.

Anonymous project HTML `https://lablab.build/ai-hackathons/vultr-hackathon/sandboxops/sandboxops-blast-radius-zero-on-vultr-compute` on this run included:

| Field | Observed value |
|---|---|
| `isDraft` | `false` |
| `createdAt` | `2026-11-05T15:54:07.881Z` |
| `repoLink` | `https://github.com/igoreduardoai/sandboxops` (no SHA) |
| `demoUrl` | `http://64.177.13.126/` |
| `demoPlatform` | `OTHER` |
| `videoLink` | non-null `.mp4` on `storage.googleapis.com` |
| `xVideoUrl` | `null` |
| `presentationLink` | a PDF on `storage.googleapis.com` |
| `categories` | `Assistant` only |
| `eventTracks` | `[]` |
| `customFieldData` | `null` |
| `techIn` | `AgentOps`, `VULTR` |
| Visible line | `Created by team SandboxOps on November 05, 2026` |
| SHA strings `bea5d33` / `1659548` | absent |

`eventTracks: []` is what the public record contained. It does not prove a hidden form field is also empty, and it does not show a saved Challenge 1 track. Category tag `Assistant` is not the same thing as the C1/C2 track. This audit did not open or edit the form.

## Rubric mapping

Only items with a source. Unknown stays unknown. Nothing here is a score.

| Claim or requirement | Source | What this run can say |
|---|---|---|
| C1 needs Serverless Inference for agent LLM calls | Event page technology section | `planner.py` targets `https://api.vultrinference.com/v1` and default model `glm-5.3` when a key is set. This run's `/health` said `planner: offline`. Live inference was not called. |
| C1 needs a Vultr VM and a web app deployed there | Event page | README and `docs/LIVE.md` name `http://64.177.13.126/` and `backend=docker`. This run did not open that host. |
| Isolated sandbox / containment moment | Event page containment focus; README | Local `network_attempt` and the bounded loop were contained. Local filesystem, `_socket`, subprocess, and `fork` were not. Docker enforcement was not run. |
| Secret hygiene | Event page | Local and stubbed runs did not pass the canary or the stub key into the child. Docker container env was not measured. |
| Resource limits and cleanup | Event page | Local CPU, address-space, and file-size limits fired. Temp cwd was removed. No pid limit locally. Docker `--rm` was not executed. |
| Real executed output, not only a description | Event page | `bill` printed `551.00` and verified. Free-form success is not auto-verified (`verified: null` under the stub). |
| Public GitHub, demo URL, video | Event page and public entry JSON | Repo link, demo URL, and a video URL are on the public entry. This run did not fetch the video or the demo. |
| Saved category / event track | Public entry JSON | `categories: [Assistant]`, `eventTracks: []`. C1 track saved: not shown. |
| Judged revision | Public entry has no SHA; demo note has `bea5d33`; tested main is `1659548` | Pin unknown. Executable trees of those two SHAs match; README does not. |
| Edits after first submit | Rule book grace-period sentence; no edit/resubmit sentence found | Unknown. No product or entry change was made. |
| Application of technology, presentation, business value, originality (1–5) | Rule book says many events use these and that the event page wins if it differs | Not scored. The event page also names those four criteria. This audit did not assign points. |

## GraveTruth harness

Requested sources were grave-truth PR 4, PR 5, and branch `cursor/evaluator-critic-loop-ad9d` at reported `4a99c8e`. This VM got HTTP 404 and `repository not found`. Nothing from that repo was copied. The scenario list in `audit/manifest.json` is for SandboxOps: journey, destructive boundaries, blast radius, dry-run versus execute, failure recovery, adversarial prompts, evidence, and the local UI. Provider behavior is offline or stubbed.

## Artifacts

- `audit/results/results.json` — every check, counts, and the deterministic restatement
- `audit/results/run-stdout.txt`, `run-stderr.txt`
- `audit/results/upstream-test_agent.json`, `upstream-test_app.json`
- `audit/results/bill.json`, `network_attempt.json`, `fork_bomb_ish.json`, `docker-missing.json`
- `audit/results/ui-probe.json` and the three PNG screenshots
- `audit/results/lighthouse-summary.json`, `lighthouse.report.json`

Product files were not modified. Findings were not patched.
