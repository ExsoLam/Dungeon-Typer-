#!/usr/bin/env python3
"""Fail when a tracked file sits outside the agreed repo layout.

The layout is described in AGENTS.md ("File layout"). Change both together.
"""
import re
import subprocess
import sys

GAME = "typing_dungeon_v48.html"

# Top-level entries that may exist. Anything else at the root fails.
ROOT = {
    ".github", ".gitignore", "AGENTS.md", "README.md", "LICENSE",
    GAME, "SOUNDS", "archive", "docs", "scripts", "server", "tests", "tools",
}

# Folder -> pattern every file under it must match.
FOLDERS = {
    "archive": r"typing_dungeon_v\d+\.html",
    "docs": r"[\w.-]+\.(md|png|jpg|svg)",
    "scripts": r"[\w.-]+\.(py|mjs|sh)",
    "tests": r"[\w.-]+\.(py|mjs)",
    "tools": r"[\w.-]+\.py",
    "server": r"(worker\.mjs|migrations/\d{4}_[\w-]+\.sql)",
    ".github": r"workflows/[\w-]+\.yml",
    "SOUNDS": r"[\w .-]+\.(mp3|ogg|wav|m4a)",
}

WHERE = {
    "html": "older game versions go in archive/; only " + GAME + " lives at the root",
    "md": "documentation goes in docs/ (README.md and AGENTS.md stay at the root)",
    "py": "desktop tools go in tools/, CI and hosting scripts in scripts/, checks in tests/",
    "mjs": "hosting scripts go in scripts/, checks in tests/, Worker code in server/",
}

files = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True).stdout.split("\0")
files = [f for f in files if f]
problems = []
for path in files:
    top, _, rest = path.partition("/")
    if top not in ROOT:
        ext = path.rsplit(".", 1)[-1]
        hint = WHERE.get(ext, "see the File layout section of AGENTS.md")
        problems.append(f"{path}: not part of the layout ({hint})")
    elif top in FOLDERS and not re.fullmatch(FOLDERS[top], rest):
        problems.append(f"{path}: does not belong in {top}/ (see the File layout section of AGENTS.md)")

if problems:
    print("Repo layout check failed:")
    print("\n".join("  " + p for p in problems))
    sys.exit(1)
print(f"Repo layout passed ({len(files)} tracked files)")
