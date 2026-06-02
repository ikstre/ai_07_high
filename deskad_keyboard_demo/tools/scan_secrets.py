#!/usr/bin/env python3
"""Stdlib-only secret scanner.

Usage:
  python tools/scan_secrets.py                     # scan staged changes
  python tools/scan_secrets.py path1 path2 ...     # scan given files/dirs
  python tools/scan_secrets.py --all               # scan tracked files

Exit code:
  0 - clean
  1 - findings (locations printed; values NEVER printed)
  2 - usage error
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "deskad_keyboard_demo"))

from backend.security import _TOKEN_SHAPED_PATTERNS, is_sensitive_key  # noqa: E402


# Files we never want to scan even if changed.
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "data/runtime",
    "static/uploads",
    "static/models",
    "static/posters",
}

# Binary-ish suffixes that are guaranteed to produce false positives.
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".glb",
    ".gltf",
    ".step",
    ".stp",
    ".safetensors",
    ".gguf",
    ".bin",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
    ".zst",
    ".log",
}

# Lines that look like "KEY=value" with a sensitive KEY trigger an alert when
# the value is not obviously a placeholder. .env.example is allowed to keep
# blank placeholders (KEY=) but never real values.
KV_LINE = re.compile(r"^(?P<key>[A-Z][A-Z0-9_]+)\s*=\s*(?P<value>.+?)\s*$")
PLACEHOLDER_VALUES = {
    "",
    "''",
    '""',
    "your-token-here",
    "<token>",
    "<your-token>",
    "changeme",
    "REPLACE_ME",
    "<redacted>",
}


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def _staged_files() -> list[Path]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [REPO_ROOT / line for line in out.splitlines() if line]


def _tracked_files() -> list[Path]:
    out = _git("ls-files")
    return [REPO_ROOT / line for line in out.splitlines() if line]


def _expand_targets(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        if target.is_dir():
            for path in target.rglob("*"):
                if path.is_file():
                    files.append(path)
        elif target.is_file():
            files.append(target)
    return files


def _should_skip(path: Path) -> bool:
    rel = path.resolve().relative_to(REPO_ROOT) if path.is_absolute() else path
    for part in rel.parts:
        if part in SKIP_DIRS:
            return True
    if rel.suffix.lower() in SKIP_SUFFIXES:
        return True
    if rel.name == "scan_secrets.py":
        return True
    if rel.name == "security.py" and rel.parts[:2] == ("deskad_keyboard_demo", "backend"):
        return True
    return False


def _scan_text(text: str, *, is_env_file: bool) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if is_env_file:
            match = KV_LINE.match(line)
            if match and is_sensitive_key(match.group("key")):
                value = match.group("value").strip().strip('"').strip("'")
                if value and value not in PLACEHOLDER_VALUES:
                    findings.append((line_no, f"env value for {match.group('key')}"))
                    continue
        for pattern in _TOKEN_SHAPED_PATTERNS:
            if pattern.search(line):
                findings.append((line_no, f"token-shaped substring matched /{pattern.pattern[:40]}/"))
                break
    return findings


def scan_paths(paths: list[Path]) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for path in paths:
        if _should_skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # .env.example never holds real values; any non-placeholder value is a finding.
        is_env = path.name.startswith(".env")
        for line_no, reason in _scan_text(text, is_env_file=is_env):
            findings.append((path, line_no, reason))
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Scan files for accidental secrets.")
    parser.add_argument("paths", nargs="*", help="Files or dirs. Default: staged changes.")
    parser.add_argument("--all", action="store_true", help="Scan every tracked file.")
    args = parser.parse_args(argv)

    if args.all and args.paths:
        parser.error("--all cannot be combined with explicit paths")

    if args.all:
        candidates = _tracked_files()
    elif args.paths:
        candidates = _expand_targets([Path(p) for p in args.paths])
    else:
        candidates = _staged_files()
        if not candidates:
            print("[scan_secrets] no staged files; pass paths or --all to scan more.")
            return 0

    findings = scan_paths(candidates)
    if not findings:
        print(f"[scan_secrets] clean ({len(candidates)} file(s) scanned).")
        return 0

    print(f"[scan_secrets] {len(findings)} potential secret(s) found:")
    for path, line, reason in findings:
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        print(f"  {rel}:{line}  -- {reason}")
    print()
    print("Values are intentionally NOT printed. Open the file at the listed line to inspect.")
    print("If this is a false positive, add the file to SKIP_DIRS/SKIP_SUFFIXES in tools/scan_secrets.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
