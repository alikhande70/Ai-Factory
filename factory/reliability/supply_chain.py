from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Iterable


ACTION_REF = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})$")
USES_LINE = re.compile(r"^\s*uses:\s*([^\s#]+)")


@dataclass(frozen=True)
class PythonDependencyInventory:
    standard_library: tuple[str, ...]
    internal: tuple[str, ...]
    external: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowActionPin:
    action: str
    sha: str


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def scan_python_imports(source_root: str | Path, *, internal_roots: Iterable[str] = ("factory",)) -> PythonDependencyInventory:
    root = Path(source_root)
    if not root.exists():
        raise FileNotFoundError(root)
    imported: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".", 1)[0])

    internal_set = set(internal_roots)
    stdlib = set(sys.stdlib_module_names)
    return PythonDependencyInventory(
        standard_library=tuple(sorted(imported & stdlib)),
        internal=tuple(sorted(imported & internal_set)),
        external=tuple(sorted(imported - stdlib - internal_set)),
    )


def verify_declared_external_dependencies(inventory: PythonDependencyInventory, *, declared: Iterable[str]) -> None:
    declared_set = set(declared)
    actual = set(inventory.external)
    undeclared = sorted(actual - declared_set)
    unused = sorted(declared_set - actual)
    if undeclared:
        raise RuntimeError(f"undeclared_python_dependencies:{','.join(undeclared)}")
    if unused:
        raise RuntimeError(f"declared_dependency_not_imported:{','.join(unused)}")


def scan_workflow_action_pins(workflow_path: str | Path) -> tuple[WorkflowActionPin, ...]:
    pins: list[WorkflowActionPin] = []
    for line in Path(workflow_path).read_text(encoding="utf-8").splitlines():
        match = USES_LINE.match(line)
        if not match:
            continue
        value = match.group(1)
        if value.startswith("./"):
            continue
        pinned = ACTION_REF.fullmatch(value)
        if pinned is None:
            raise RuntimeError(f"workflow_action_not_sha_pinned:{value}")
        pins.append(WorkflowActionPin(action=pinned.group(1), sha=pinned.group(2)))
    return tuple(pins)


def build_sbom(repo_root: str | Path, *, declared_external: Iterable[str] = ()) -> dict[str, object]:
    root = Path(repo_root)
    inventory = scan_python_imports(root / "factory")
    verify_declared_external_dependencies(inventory, declared=declared_external)
    actions = scan_workflow_action_pins(root / ".github" / "workflows" / "test.yml")
    payload: dict[str, object] = {
        "format": "AI_FACTORY_SBOM_V1",
        "python": {
            "external_dependencies": list(inventory.external),
            "standard_library_imports": list(inventory.standard_library),
            "internal_roots": list(inventory.internal),
        },
        "github_actions": [asdict(item) for item in actions],
    }
    payload["fingerprint"] = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return payload


def verify_sbom_fingerprint(sbom: dict[str, object]) -> None:
    supplied = sbom.get("fingerprint")
    if not isinstance(supplied, str):
        raise ValueError("sbom fingerprint missing")
    unsigned = dict(sbom)
    unsigned.pop("fingerprint", None)
    calculated = hashlib.sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
    if calculated != supplied:
        raise ValueError("sbom fingerprint mismatch")
