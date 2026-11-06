"""Generate private deployment settings; never overwrite or print secrets."""

import argparse
import os
import re
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--domain", help="DNS name already pointing to this EC2 instance")
args = parser.parse_args()
domain = args.domain
if domain and not re.fullmatch(r"(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", domain):
    parser.error("Use a DNS hostname, without https://, port or path.")
target = Path(__file__).resolve().parent / ".env"
origin = f"https://{domain}" if domain else "http://localhost:8090"
content = (
    "# Private deployment configuration. Do not commit or share.\n"
    f"SITE_ADDRESS={domain or origin}\nPUBLIC_ORIGIN={origin}\n"
    f"EDGE_BIND={'0.0.0.0' if domain else '127.0.0.1'}\n"
    f"COOKIE_SECURE={'true' if domain else 'false'}\n"
    f"APP_API_KEY={secrets.token_urlsafe(48)}\n"
    f"DATABASE_PASSWORD={secrets.token_urlsafe(32)}\n"
    "MOCK_MODE=true\nEVON_CONTEXT_TOKENS=4096\nEVON_TIMEOUT_SECONDS=120\n"
    "GNANI_API_KEY=\nEVON_API_KEY=\n"
)
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
        output.write(content)
except FileExistsError:
    parser.exit(1, "deploy/.env already exists; edit it deliberately. Nothing overwritten.\n")
print(f"Created private deploy/.env. Mode: MOCK. Browser origin: {origin}")
if not domain:
    print("Loopback-only preview: connect using the SSH tunnel in FULL_STACK.md.")
