#!/usr/bin/env python3
"""Guard: the plugin backend must import nothing outside the standard library.

A third-party import would mean the plugin ZIP needs vendored wheels,
which in turn means Docker or the Decky CLI to build it. Keeping this
true is what lets the release workflow be a plain file copy, so it is
worth a CI check rather than a code-review convention.
"""

from __future__ import annotations

import ast
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCANNED = ("main.py", "py_modules")

#: Injected by the decky loader at runtime, not installed from PyPI.
ALLOWED_NON_STDLIB = frozenset({"decky"})

#: The plugin's own package.
FIRST_PARTY = frozenset({"steamview"})


def python_files() -> list[str]:
    found: list[str] = []
    for target in SCANNED:
        path = os.path.join(REPO_ROOT, target)
        if os.path.isfile(path):
            found.append(path)
        elif os.path.isdir(path):
            for directory, subdirs, filenames in os.walk(path):
                subdirs[:] = [d for d in subdirs if d != "__pycache__"]
                found.extend(
                    os.path.join(directory, name) for name in filenames if name.endswith(".py")
                )
    return sorted(found)


def top_level_imports(path: str) -> set[str]:
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # A relative import stays inside the plugin.
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def main() -> int:
    stdlib = set(sys.stdlib_module_names)
    allowed = stdlib | ALLOWED_NON_STDLIB | FIRST_PARTY

    violations: list[str] = []
    for path in python_files():
        for name in sorted(top_level_imports(path) - allowed):
            violations.append(f"{os.path.relpath(path, REPO_ROOT)}: imports {name!r}")

    if violations:
        print("Backend imports outside the standard library:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(
            "\nThe plugin backend must stay stdlib-only so the ZIP can be built "
            "without Docker or the Decky CLI. Discuss before adding a dependency.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(python_files())} backend files import only the standard library.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
