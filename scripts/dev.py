"""Run the local React + Spring + Python studio. Mock providers by default."""

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real", action="store_true", help="Use configured real providers (can incur charges)"
    )
    args = parser.parse_args()
    java = shutil.which("java")
    if not java:
        candidates = sorted((ROOT / ".tools/jdk").glob("*/bin/java.exe"))
        java = str(candidates[-1]) if candidates else None
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    jar = ROOT / "gateway/target/gateway-1.0.0.jar"
    if not java or not npm or not jar.exists() or not (ROOT / "frontend/node_modules").exists():
        parser.error("Build the gateway and install frontend dependencies first; see FULL_STACK.md.")
    for port in (8123, 8081, 5173):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                parser.error(f"Port {port} is already in use. Stop your previous studio launcher first.")
    env = os.environ.copy()
    env.update(
        DEBUG="false",
        APP_API_KEY=secrets.token_urlsafe(48),
        APP_ENV="development",
        MOCK_MODE="false" if args.real else "true",
        AI_SERVICE_URL="http://127.0.0.1:8123",
        PUBLIC_ORIGIN="http://localhost:5173",
        COOKIE_SECURE="false",
        BIND_ADDRESS="127.0.0.1",
        DATABASE_URL=os.environ.get(
            "DATABASE_URL",
            "jdbc:postgresql://127.0.0.1:5432/callshield",
        ),
        DATABASE_USER=os.environ.get("DATABASE_USER", "callshield"),
        DATABASE_PASSWORD=os.environ.get("DATABASE_PASSWORD", "callshield_local"),
    )
    if args.real:
        # Fail before launching Java/React; never print raw Settings validation inputs or secrets.
        sys.path.insert(0, str(ROOT))
        from app.config import Settings

        try:
            configured = Settings(
                _env_file=ROOT / ".env",
                app_env="development",
                mock_mode=False,
                app_api_key=env["APP_API_KEY"],
            )
        except ValueError:
            parser.error("Invalid real-provider configuration. Check root .env using REAL_TESTING.md.")
        if configured.evon_context_tokens < 2048:
            parser.error(
                "Structured Evon needs more context. Set EVON_CONTEXT_TOKENS=4096 and restart EC2 llama-server with -c 4096."
            )
        if (
            configured.prisma_enabled or configured.timbre_enabled
        ) and not configured.gnani_api_key.get_secret_value():
            parser.error(
                "Real speech is enabled but GNANI_API_KEY is missing in root .env. Use your issued key."
            )
        print(
            "Real configuration loaded. Provider connectivity and credentials still require verification.",
            flush=True,
        )
    children = []
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        commands = [
            (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8123",
                    "--no-access-log",
                ],
                ROOT,
            ),
            ([java, "-jar", str(jar)], ROOT),
            ([npm, "run", "dev"], ROOT / "frontend"),
        ]
        for command, cwd in commands:
            children.append(
                subprocess.Popen(
                    command, cwd=cwd, env=env, creationflags=creation, stdout=sys.stdout, stderr=sys.stderr
                )
            )
        print(
            f"\nCallShield studio: http://localhost:5173 | {'REAL providers' if args.real else 'MOCK providers'}\nCreate an account in the UI. Ctrl+C stops all three services.\n",
            flush=True,
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        if any(child.poll() not in (None, 0) for child in children):
            raise RuntimeError("A service stopped unexpectedly. Read its startup error above.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(children):
            if child.poll() is None:
                # npm.cmd creates a Vite child on Windows: stop only this owned process tree.
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    main()
