#!/usr/bin/env python3
"""Assemble the installable plugin ZIP.

Decky expects a ZIP containing a single top-level directory named after
the plugin, holding the plugin's files. Because this backend is pure
standard library with no compiled parts, packaging is just a file copy --
no Docker image and no Decky CLI required, which is what keeps CI simple.

Only the files the loader actually needs are included. Sources, tests and
tooling are deliberately left out.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Files that must exist, or packaging fails loudly rather than shipping
#: a plugin that will not load.
REQUIRED_FILES = (
    "plugin.json",
    "package.json",
    "main.py",
    "LICENSE",
    "README.md",
    "dist/index.js",
)

#: Optional extras copied when present.
OPTIONAL_FILES = ("CHANGELOG.md",)

#: Directory trees copied wholesale when present.
INCLUDED_TREES = ("py_modules", "defaults", "assets")

#: Never ship these, wherever they appear inside an included tree.
EXCLUDED_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"})
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".tmp")


def read_plugin_name() -> str:
    with open(os.path.join(REPO_ROOT, "plugin.json"), "r", encoding="utf-8") as handle:
        name = json.load(handle).get("name")
    if not isinstance(name, str) or not name.strip():
        raise SystemExit("plugin.json has no usable 'name'")
    return name.strip()


def read_version() -> str:
    with open(os.path.join(REPO_ROOT, "package.json"), "r", encoding="utf-8") as handle:
        version = json.load(handle).get("version")
    if not isinstance(version, str) or not version.strip():
        raise SystemExit("package.json has no usable 'version'")
    return version.strip()


def _is_excluded(path: str) -> bool:
    return path.endswith(EXCLUDED_SUFFIXES)


def collect_files() -> list[tuple[str, str]]:
    """(absolute source, path relative to the plugin dir) pairs."""
    collected: list[tuple[str, str]] = []

    missing = [name for name in REQUIRED_FILES if not os.path.isfile(os.path.join(REPO_ROOT, name))]
    if missing:
        raise SystemExit(
            "cannot package, these required files are missing: "
            + ", ".join(missing)
            + "\n(did you run `pnpm run build` first?)"
        )

    for name in REQUIRED_FILES + OPTIONAL_FILES:
        source = os.path.join(REPO_ROOT, name)
        if os.path.isfile(source):
            collected.append((source, name))

    for tree in INCLUDED_TREES:
        root = os.path.join(REPO_ROOT, tree)
        if not os.path.isdir(root):
            continue
        for directory, subdirs, filenames in os.walk(root):
            subdirs[:] = [d for d in subdirs if d not in EXCLUDED_DIR_NAMES]
            for filename in sorted(filenames):
                source = os.path.join(directory, filename)
                if _is_excluded(source):
                    continue
                collected.append((source, os.path.relpath(source, REPO_ROOT)))

    return collected


def build_zip(out_dir: str) -> str:
    plugin_name = read_plugin_name()
    version = read_version()
    os.makedirs(out_dir, exist_ok=True)

    archive_name = f"{plugin_name}-v{version}.zip"
    archive_path = os.path.join(out_dir, archive_name)

    files = collect_files()
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, relative in files:
            # Everything lives under a single top-level plugin directory,
            # which is the layout Decky's installer expects.
            archive.write(source, os.path.join(plugin_name, relative))

    print(f"Packaged {len(files)} files into {archive_path}")
    for _, relative in sorted(files, key=lambda pair: pair[1]):
        print(f"  {plugin_name}/{relative}")
    return archive_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="out", help="where to write the ZIP (default: out)")
    args = parser.parse_args()

    archive_path = build_zip(os.path.join(REPO_ROOT, args.out_dir))

    # Hand the filename back to the release workflow.
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"name={os.path.basename(archive_path)}\n")
            handle.write(f"path={archive_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
