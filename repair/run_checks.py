#!/usr/bin/env python3
"""Re-run the allowlisted repair checks. Does not apply patches or shell from model output."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    [sys.executable, "test_agent.py"],
    [sys.executable, "test_app.py"],
)


def main():
    failed = 0
    for command in COMMANDS:
        print("RUN", " ".join(command), flush=True)
        completed = subprocess.run(command, cwd=ROOT)
        print("EXIT", completed.returncode, " ".join(command), flush=True)
        if completed.returncode != 0:
            failed += 1
    print(f"commands_failed {failed}/{len(COMMANDS)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
