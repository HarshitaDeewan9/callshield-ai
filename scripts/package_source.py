"""Create an EC2 source archive from explicit source roots, excluding runtime data/secrets."""

import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist/callshield-source.tar.gz"
ROOTS = ("app", "frontend", "gateway", "scripts", "deploy", "tests")
EXCLUDE = {
    "node_modules",
    "dist",
    "target",
    "data",
    "__pycache__",
    "test-results",
    ".pytest_cache",
    ".ruff_cache",
}
EXTENSIONS = {
    ".py",
    ".java",
    ".md",
    ".json",
    ".ts",
    ".tsx",
    ".css",
    ".html",
    ".svg",
    ".js",
    ".yml",
    ".yaml",
    ".sql",
    ".xml",
    ".toml",
}


def allowed(path):
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and not path.is_symlink()
        and not any(part in EXCLUDE or part.startswith(".") for part in relative.parts)
        and (path.suffix in EXTENSIONS or path.name in ("Dockerfile", "Caddyfile"))
    )


def main():
    TARGET.parent.mkdir(exist_ok=True)
    files = []
    for folder in ROOTS:
        for directory, children, filenames in os.walk(ROOT / folder):
            children[:] = [name for name in children if name not in EXCLUDE and not name.startswith(".")]
            files.extend(path for name in filenames if allowed(path := Path(directory) / name))
    files += list(ROOT.glob("*.md"))
    files += [ROOT / name for name in ("pyproject.toml", "Dockerfile", ".dockerignore", ".gitignore")]
    with tarfile.open(TARGET, "w:gz") as archive:
        for path in sorted(set(files)):
            archive.add(path, arcname="callshield-ai/" + path.relative_to(ROOT).as_posix(), recursive=False)
    with tarfile.open(TARGET) as archive:
        names = archive.getnames()
        assert all(not name.endswith((".pem", ".key", ".gguf", ".wav", "/.env")) for name in names)
        assert "callshield-ai/frontend/package-lock.json" in names
        assert "callshield-ai/deploy/compose.yml" in names
    print(
        f"Created {TARGET.relative_to(ROOT)} ({len(names)} source files). Secrets, tools, databases and model files excluded."
    )


if __name__ == "__main__":
    main()
