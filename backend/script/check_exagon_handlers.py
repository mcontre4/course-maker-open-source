#!/usr/bin/env python3
"""
Hexagonal boundary checker — generic, role-based import enforcement.

Enforces AGENTS.md dependency direction:
    adapters -> application services -> domain
without enumerating every domain by name. New domains under
src/app/<domain>/ are auto-discovered and enforced by *role*.

Roles are derived from the file path:
    app/shared/domain/*            -> shared_domain
    app/shared/application/*       -> shared_application
    app/shared/infrastructure/*    -> shared_infrastructure
    app/<domain>/domain/*          -> domain
    app/<domain>/ports/*           -> ports
    app/<domain>/application/*     -> application
    app/<domain>/adapters/**/*     -> adapters
    app/main.py, app/composition.py, app/<domain>/composition.py
                                   -> composition_root (wiring, may import anything)

Rules
-----
* shared_domain:      may only import stdlib + app.shared.domain
* domain:             may only import stdlib + app.shared.domain + own app.<domain>.domain
* ports:              may only import stdlib + app.shared.domain + own domain
* shared_application: may only import stdlib + app.shared.domain + app.shared.application
* application:        may only import stdlib + shared domain/application + own domain/ports/application
* shared_infrastructure: may only import stdlib + shared domain/application/infrastructure
* adapters:           may only import stdlib + shared * + own domain/ports/application/adapters (+ shared infra)
* composition_root:   unrestricted (must stay at the edge; not counted as business logic)

Additionally, domain/ports may not import infrastructure/framework libs
(sqlalchemy, fastapi, redis, psycopg, alembic, uvicorn, langchain, langgraph).

Usage:
    python backend/scripts/check_hexagonal_boundaries.py
    python backend/scripts/check_hexagonal_boundaries.py --root backend/src
Exit 0 = clean, 1 = violations found.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — keep in sync with AGENTS.md
# ---------------------------------------------------------------------------

# Framework / infra libs that must never leak into domain or ports.
FORBIDDEN_EXTERNALS_FOR_DOMAIN_AND_PORTS = {
    "sqlalchemy",
    "fastapi",
    "redis",
    "psycopg",
    "alembic",
    "uvicorn",
    "langchain",
    "langgraph",
}

# Domain/ports should never pull these app layers either.
FORBIDDEN_APP_PREFIXES_FOR_DOMAIN = (
    "app.shared.application",
    "app.shared.infrastructure",
    "app.users.application",
    "app.users.ports",
    "app.users.adapters",
    "app.users.composition",
    "app.main",
    "app.composition",
)

# ---------------------------------------------------------------------------
# Role detection
# ---------------------------------------------------------------------------


def get_role_and_domain(module: str) -> tuple[str, str | None]:
    """Return (role, domain_name) for a dotted module name.

    domain_name is e.g. 'users' for app.users.domain, 'shared' for
    app.shared.*, None for top-level like app.main.
    """
    parts = module.split(".")

    # Composition roots: app.main, app.composition, app.<domain>.composition
    if module in {"app.main", "app.composition"} or module.endswith(".composition"):
        return "composition_root", None

    if len(parts) < 3:
        # e.g. app.users, app.shared — treat as neutral (should not contain logic)
        return "composition_root", None

    # parts[0]=app, parts[1]=domain/shared, parts[2]=layer
    owner = parts[1]
    layer = parts[2]

    if owner == "shared":
        if layer == "domain":
            return "shared_domain", "shared"
        if layer == "application":
            return "shared_application", "shared"
        if layer == "infrastructure":
            return "shared_infrastructure", "shared"
        # shared/adapters should not exist; fall through
        return "composition_root", None

    # <domain>/*
    if layer == "domain":
        return "domain", owner
    if layer == "ports":
        return "ports", owner
    if layer == "application":
        return "application", owner
    if layer == "adapters":
        return "adapters", owner

    # Unknown layer like app.users.foo -> treat as composition so we don't
    # false-positive on wiring code; add explicit handling if you add layers.
    return "composition_root", None


def allowed_app_prefixes(role: str, domain: str | None) -> tuple[str, ...] | None:
    """Return allowed `app.*` prefixes for the role. None = unrestricted."""
    if role == "composition_root":
        return None
    if role == "shared_domain":
        return ("app.shared.domain",)
    if role == "shared_application":
        return ("app.shared.domain", "app.shared.application")
    if role == "shared_infrastructure":
        return (
            "app.shared.domain",
            "app.shared.application",
            "app.shared.infrastructure",
        )
    if role == "domain":
        assert domain is not None
        return ("app.shared.domain", f"app.{domain}.domain")
    if role == "ports":
        assert domain is not None
        # ports define protocols over domain types; never over application/adapters
        return ("app.shared.domain", f"app.{domain}.domain", f"app.{domain}.ports")
    if role == "application":
        assert domain is not None
        return (
            "app.shared.domain",
            "app.shared.application",
            f"app.{domain}.domain",
            f"app.{domain}.ports",
            f"app.{domain}.application",
        )
    if role == "adapters":
        assert domain is not None
        return (
            "app.shared.domain",
            "app.shared.application",
            "app.shared.infrastructure",
            f"app.{domain}.domain",
            f"app.{domain}.ports",
            f"app.{domain}.application",
            f"app.{domain}.adapters",
        )
    return None


def is_allowed_app_import(role: str, domain: str | None, imported: str) -> bool:
    allowed = allowed_app_prefixes(role, domain)
    if allowed is None:
        return True
    return any(imported == p or imported.startswith(p + ".") for p in allowed)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def resolve_relative_import(
    current_module: str, level: int, module: str | None
) -> str | None:
    """Resolve `from .[.]*module import ...` to an absolute dotted path."""
    if level == 0:
        return module
    # Package is everything except the leaf module: app.users.domain.user -> app.users.domain
    package = current_module.rsplit(".", 1)[0] if "." in current_module else current_module
    pkg_parts = package.split(".")
    # level 1 = current package, level 2 = parent, etc.
    if level - 1 > len(pkg_parts):
        return None  # beyond top-level — ignore
    base_parts = pkg_parts[: len(pkg_parts) - (level - 1)] if level > 1 else pkg_parts
    base = ".".join(base_parts)
    if module is None:
        return base or None
    return f"{base}.{module}" if base else module


def collect_imports(tree: ast.AST, current_module: str) -> list[tuple[int, str]]:
    """Return list of (lineno, absolute_imported_module) for each import."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            abs_mod = resolve_relative_import(current_module, node.level, node.module)
            # `from . import foo` — each name is a submodule of abs_mod
            if node.module is None:
                # from . import foo, bar
                if abs_mod is None:
                    continue
                for alias in node.names:
                    # from . import foo  ->  app.users.domain.foo
                    imported = f"{abs_mod}.{alias.name}" if alias.name != "*" else abs_mod
                    out.append((node.lineno, imported))
            else:
                if abs_mod is None:
                    continue
                out.append((node.lineno, abs_mod))
    return out


# ---------------------------------------------------------------------------
# File -> module mapping
# ---------------------------------------------------------------------------


def file_to_module(root: Path, file: Path) -> str | None:
    """Convert backend/src/app/users/domain/user.py -> app.users.domain.user."""
    try:
        rel = file.relative_to(root)
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.with_suffix("").parts)
    # Drop __init__ leaf: app/users/domain/__init__.py -> app.users.domain
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

Violation = tuple[Path, int, str]


def check_file(root: Path, file: Path) -> list[Violation]:
    module = file_to_module(root, file)
    if module is None:
        return []
    # Only enforce under app.* (ignore tests, scripts, etc.)
    if not module.startswith("app."):
        return []
    role, domain = get_role_and_domain(module)
    if role == "composition_root":
        return []

    try:
        source = file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file))
    except SyntaxError as exc:
        return [(file, exc.lineno or 0, f"syntax error: {exc.msg}")]

    violations: list[Violation] = []
    for lineno, imported in collect_imports(tree, module):
        # External infra leak into domain/ports
        if role in {"shared_domain", "domain", "ports"}:
            top = imported.split(".")[0]
            if top in FORBIDDEN_EXTERNALS_FOR_DOMAIN_AND_PORTS:
                violations.append(
                    (
                        file,
                        lineno,
                        f"{role} ({module}) must not import infra lib '{imported}' "
                        f"(domain/ports must be framework-free)",
                    )
                )
            # Hard forbidden app prefixes (broader guard for cross-layer leaks)
            if role in {"shared_domain", "domain"}:
                if any(
                    imported == p or imported.startswith(p + ".")
                    for p in FORBIDDEN_APP_PREFIXES_FOR_DOMAIN
                ):
                    violations.append(
                        (
                            file,
                            lineno,
                            f"{role} ({module}) must not import '{imported}' "
                            f"(domain must be pure; allowed: {allowed_app_prefixes(role, domain)})",
                        )
                    )
                    continue

        # Generic app.* prefix allowlist
        if imported.startswith("app."):
            if not is_allowed_app_import(role, domain, imported):
                violations.append(
                    (
                        file,
                        lineno,
                        f"{role} ({module}) must not import '{imported}' "
                        f"(allowed: {allowed_app_prefixes(role, domain)})",
                    )
                )

    return violations


def run(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    for file in root.rglob("*.py"):
        # Skip caches
        if "__pycache__" in file.parts:
            continue
        violations.extend(check_file(root, file))
    return sorted(violations)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check hexagonal import boundaries.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("backend/src"),
        help="Source root containing the `app` package (default: backend/src).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print clean files as well.",
    )
    args = parser.parse_args()

    root: Path = args.root.resolve()
    # Support --root backend/src or backend/src/app
    if root.name == "app" and root.is_dir():
        root = root.parent
    if not (root / "app").is_dir():
        print(f"error: --root must contain an `app` package, got {args.root}", file=sys.stderr)
        print(f"  resolved root: {root}", file=sys.stderr)
        return 2

    violations = run(root)

    if violations:
        print(f"Hexagonal boundary check FAILED — {len(violations)} violation(s):\n", file=sys.stderr)
        for file, lineno, msg in violations:
            rel = file.relative_to(Path.cwd()) if file.is_absolute() else file
            print(f"  {rel}:{lineno}: {msg}", file=sys.stderr)
        print(
            "\nDependency direction must be adapters -> application -> domain.\n"
            "Fix by moving the import inward (or moving the code to the correct layer).",
            file=sys.stderr,
        )
        return 1

    print("Hexagonal boundary check OK — all imports respect adapters -> application -> domain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
