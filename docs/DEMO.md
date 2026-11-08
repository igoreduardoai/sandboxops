# Demo script for this candidate

Use this on a machine where `python3 repair/run_checks.py` has already exited 0. Do not point this script at the public demo host. This branch was not deployed there.

1. Start `python3 app.py` and open `http://127.0.0.1:8080/`.
2. Read the health line. On a machine without `SANDBOX=docker` and with the namespace helper working, it should include `execution: namespace` and `planner: offline`.
3. Press `bill`. The banner should say `VERIFIED: 551.00`. The JSON `sandbox.backend` should be `namespace`, `executed` should be true, and `sha256` should match the JSON object with that field removed.
4. Press `network_attempt`. The banner should say `CONTAINED`. The stderr should be a name-resolution or network error from inside the jail, not a successful connection.
5. Press `fork_bomb_ish` and wait a few seconds. The banner should say `CONTAINED` and the record should include `sandbox-signal`.
6. Check `Dry run` and press `bill` again. The banner should say `DRY RUN: not executed`. `verified` should be false.
7. Stop the server, start it with `SANDBOX=docker` and no Docker installed, and press `bill`. The banner should say `UNAVAILABLE`. Nothing in that response is a container result.

What not to say from this script: that Docker was observed, that Vultr inference ran, that the public URL serves this commit, or that the blast radius is zero.
