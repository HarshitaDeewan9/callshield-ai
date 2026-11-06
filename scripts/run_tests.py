"""Run offline tests without reusing another process/account's pytest temp or cache folders."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    project = Path(__file__).resolve().parents[1]
    # Each invocation owns a new directory; never delete/reuse pytest-of-USER or .pytest_cache.
    with tempfile.TemporaryDirectory(prefix="callshield-tests-", ignore_cleanup_errors=True) as directory:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(Path(directory) / "pytest"),
                *sys.argv[1:],
            ],
            cwd=project,
            env={
                **os.environ,
                "MOCK_MODE": "true",
                "APP_ENV": "development",
                "RUN_REAL_INTEGRATION": "false",
            },
            check=False,
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
