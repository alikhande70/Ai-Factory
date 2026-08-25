from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from factory.reliability.supply_chain import (
    build_sbom,
    scan_python_imports,
    scan_workflow_action_pins,
    verify_declared_external_dependencies,
    verify_sbom_fingerprint,
)


class Phase11SupplyChainTests(unittest.TestCase):
    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def test_production_factory_has_no_undeclared_external_python_dependencies(self) -> None:
        inventory = scan_python_imports(self.repo_root / "factory")
        verify_declared_external_dependencies(inventory, declared=())
        self.assertEqual(inventory.external, ())

    def test_ci_actions_are_exact_commit_sha_pinned(self) -> None:
        pins = scan_workflow_action_pins(self.repo_root / ".github" / "workflows" / "test.yml")
        self.assertGreaterEqual(len(pins), 2)
        for pin in pins:
            self.assertRegex(pin.sha, r"^[0-9a-f]{40}$")

    def test_unpinned_workflow_action_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow = Path(tmp) / "test.yml"
            workflow.write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "workflow_action_not_sha_pinned"):
                scan_workflow_action_pins(workflow)

    def test_undeclared_python_dependency_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "module.py").write_text("import requests\n", encoding="utf-8")
            inventory = scan_python_imports(root, internal_roots=())
            with self.assertRaisesRegex(RuntimeError, "undeclared_python_dependencies:requests"):
                verify_declared_external_dependencies(inventory, declared=())

    def test_sbom_is_fingerprinted_and_tamper_detectable(self) -> None:
        sbom = build_sbom(self.repo_root, declared_external=())
        verify_sbom_fingerprint(sbom)
        self.assertEqual(sbom["format"], "AI_FACTORY_SBOM_V1")
        encoded = json.dumps(sbom)
        self.assertIn("actions/checkout", encoded)
        tampered = json.loads(encoded)
        tampered["python"]["external_dependencies"] = ["unexpected"]
        with self.assertRaisesRegex(ValueError, "sbom fingerprint mismatch"):
            verify_sbom_fingerprint(tampered)

    def test_sbom_schema_is_value_bounded_and_machine_readable(self) -> None:
        schema = json.loads((self.repo_root / "schemas" / "sbom.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["format"]["const"], "AI_FACTORY_SBOM_V1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["github_actions"]["items"]["properties"]["sha"]["pattern"], "^[0-9a-f]{40}$")
        self.assertEqual(schema["properties"]["fingerprint"]["pattern"], "^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
