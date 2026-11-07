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

# Framework / infra libs that must never leak into domain/ports/application.
FORBIDDEN_EXTERNALS_FOR_INNER_LAYERS = {
    "sqlalchemy",
    "fastapi",
    "redis",
    "psycopg",
    "alembic",
    "uvicorn",
    "langchain",
    "langgraph",
}

# Keep alias for backward compatibility
FORBIDDEN_EXTERNALS_FOR_DOMAIN_AND_PORTS = FORBIDDEN_EXTERNALS_FOR_INNER_LAYERS

# Volatile stdlib that must go through ports (Clock/IdGenerator) in inner layers.
FORBIDDEN_STDLIB_FOR_INNER_LAYERS = {
    "uuid",
    "datetime",
}

# Composition-only infra that must not be constructed outside composition_root.
FORBIDDEN_COMPOSITION_IMPORTS_FOR_NON_ROOT = {
    "app.shared.infrastructure.database",
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


def _is_allowed_stdlib_import(role: str, imported: str, file: Path) -> bool:
    """Allow stdlib volatile imports only where ports are defined or implemented."""
    # shared_domain is allowed to define Clock/IdGenerator protocols and PrefixedUuid
    # shared_infrastructure is allowed to implement them
    # adapters may also use them via infrastructure adapters
    if role in {"shared_domain", "shared_infrastructure", "adapters", "composition_root"}:
        return True
    # shared_application defines UnitOfWork port — no stdlib volatile needed
    top = imported.split(".")[0]
    if top in FORBIDDEN_STDLIB_FOR_INNER_LAYERS:
        # Allow `from app.shared.domain.clock import Clock` (app import, not stdlib)
        # but forbid `import uuid` / `import datetime` in domain/ports/application
        # Exception: shared_domain owns PrefixedUuid which needs uuid/typing — allow uuid only there
        if role == "shared_domain":
            return True
        return False
    return True


def _check_use_case_boundaries(
    tree: ast.AST, module: str, role: str, file: Path
) -> list[Violation]:
    violations: list[Violation] = []
    if role != "application":
        return violations
    # Enforce single public method `execute` per application service
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for cls in classes:
        public_methods = [
            n.name
            for n in cls.body
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
        ]
        if len(public_methods) > 1:
            violations.append(
                (
                    file,
                    cls.lineno,
                    f"application ({module}).{cls.name} must have a single public method `execute` "
                    f"(found {public_methods}) — one class = one use case (Clean Architecture interactor)",
                )
            )
        if public_methods and public_methods != ["execute"]:
            violations.append(
                (
                    file,
                    cls.lineno,
                    f"application ({module}).{cls.name} public method must be named `execute` "
                    f"(found {public_methods})",
                )
            )
    # Enforce Request/Response DTOs: execute must take a Request DTO, not primitives soup
    # Heuristic: check that `execute` has an arg annotated with `Request` in name
    for cls in classes:
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name == "execute":
                args = node.args.args  # includes self
                # expect def execute(self, request: CreateUserRequest)
                if len(args) == 2:  # self + one arg
                    ann = args[1].annotation
                    if ann is not None:
                        ann_text = ast.unparse(ann) if hasattr(ast, "unparse") else ""
                        if "Request" not in ann_text:
                            violations.append(
                                (
                                    file,
                                    node.lineno,
                                    f"application ({module}).{cls.name}.execute must take a single Request DTO "
                                    f"(e.g. CreateUserRequest), found annotation `{ann_text}`",
                                )
                            )
                elif len(args) > 2:
                    violations.append(
                        (
                            file,
                            node.lineno,
                            f"application ({module}).{cls.name}.execute must take a single Request DTO, "
                            f"not {len(args)-1} primitive args (use CreateUserRequest)",
                        )
                    )
    return violations


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

    # Use-case boundary checks (single method, Request DTO)
    violations.extend(_check_use_case_boundaries(tree, module, role, file))

    for lineno, imported in collect_imports(tree, module):
        # External infra leak into inner layers (domain/ports/application/shared_*)
        if role in {"shared_domain", "shared_application", "domain", "ports", "application"}:
            top = imported.split(".")[0]
            if top in FORBIDDEN_EXTERNALS_FOR_INNER_LAYERS:
                violations.append(
                    (
                        file,
                        lineno,
                        f"{role} ({module}) must not import infra lib '{imported}' "
                        f"(inner layers must be framework-free; use ports/adapters)",
                    )
                )
            if not _is_allowed_stdlib_import(role, imported, file):
                violations.append(
                    (
                        file,
                        lineno,
                        f"{role} ({module}) must not import volatile stdlib '{imported}' "
                        f"(use Clock/IdGenerator ports via DI)",
                    )
                )
            # Composition-only infra must not be used outside composition_root
            if any(
                imported == p or imported.startswith(p + ".")
                for p in FORBIDDEN_COMPOSITION_IMPORTS_FOR_NON_ROOT
            ):
                violations.append(
                    (
                        file,
                        lineno,
                        f"{role} ({module}) must not import composition infra '{imported}' "
                        f"(only composition_root may construct Session/Engine)",
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

        # Generic app.* prefix allowlist (cross-domain isolation)
        if imported.startswith("app."):
            if not is_allowed_app_import(role, domain, imported):
                violations.append(
                    (
                        file,
                        lineno,
                        f"{role} ({module}) must not import '{imported}' "
                        f"(allowed: {allowed_app_prefixes(role, domain)}; cross-domain imports forbidden)",
                    )
                )
            # Explicit cross-domain check for clearer message
            if role in {"domain", "ports", "application", "adapters"} and domain is not None:
                for other in _all_domains(root):
                    if other != domain and imported.startswith(f"app.{other}."):
                        violations.append(
                            (
                                file,
                                lineno,
                                f"{role} ({module}) must not import cross-domain '{imported}' "
                                f"(domains are independent; share via app.shared.* or events)",
                            )
                        )

    # Calls through an injected Clock port are the intended dependency boundary.
    clock_receivers: set[str] = set()
    for constructor in ast.walk(tree):
        if not isinstance(constructor, ast.FunctionDef) or constructor.name != "__init__":
            continue
        clock_args = {
            arg.arg for arg in constructor.args.args
            if isinstance(arg.annotation, ast.Name) and arg.annotation.id == "Clock"
        }
        for assignment in ast.walk(constructor):
            if not isinstance(assignment, ast.Assign):
                continue
            for target in assignment.targets:
                pairs = [(target, assignment.value)]
                if isinstance(target, ast.Tuple) and isinstance(assignment.value, ast.Tuple):
                    pairs = list(zip(target.elts, assignment.value.elts, strict=False))
                for destination, source in pairs:
                    if isinstance(source, ast.Name) and source.id in clock_args:
                        # Ignore Load/Store context when comparing the receiver.
                        clock_receivers.add(ast.unparse(destination))

    # Also check for direct volatile calls like uuid4() / datetime.now() in inner layers
    if role in {"domain", "ports", "application", "shared_domain", "shared_application"}:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name in {"uuid4", "now"}:
                    if (
                        func_name == "now"
                        and isinstance(node.func, ast.Attribute)
                        and ast.unparse(node.func.value) in clock_receivers
                    ):
                        continue
                    # SystemClock/UuidIdGenerator are in shared_infrastructure, not checked here
                    violations.append(
                        (
                            file,
                            node.lineno,
                            f"{role} ({module}) must not call '{func_name}()' directly "
                            f"(use IdGenerator/Clock port via DI)",
                        )
                    )

    return violations


def _all_domains(root: Path) -> set[str]:
    domains: set[str] = set()
    app_root = root / "app"
    if not app_root.is_dir():
        return domains
    for child in app_root.iterdir():
        if child.is_dir() and child.name not in {"shared", "__pycache__"}:
            # consider it a domain if it has domain/ or application/ etc.
            if any((child / sub).is_dir() for sub in ("domain", "application", "ports", "adapters")):
                domains.add(child.name)
    return domains


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
