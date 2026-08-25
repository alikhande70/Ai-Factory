from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from factory.evaluations.store import SQLiteEvaluationStore
from factory.runtime.secrets import (
    REDACTED_SECRET,
    SecretBinding,
    SecretBroker,
    SecretMaterial,
    SecretReference,
)
from factory.runtime.tracing import REDACTED, SQLiteTracer


class FakeSecretProvider:
    provider_name = "test-vault"

    def __init__(self, values: dict[str, str]) -> None:
        self._values = dict(values)
        self.resolve_calls: list[str] = []

    def resolve(self, reference: SecretReference) -> str:
        self.resolve_calls.append(reference.secret_id)
        return self._values[reference.secret_id]


class Phase11SecretReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reference = SecretReference(
            secret_id="github-prod-token",
            provider="test-vault",
            mission_id="MISSION-001",
            required_capability="github.write",
            purpose="publish reviewed source changes",
            version="7",
        )
        self.provider = FakeSecretProvider({"github-prod-token": "super-secret-value-123"})
        self.broker = SecretBroker({"test-vault": self.provider})

    def test_broker_injects_only_requested_scoped_secret_into_executor(self) -> None:
        observed: dict[str, str] = {}

        def executor(env: dict[str, str]) -> str:
            observed.update(env)
            return "ok"

        result = self.broker.execute_with_bindings(
            mission_id="MISSION-001",
            actor_id="A11",
            agent_capabilities=("github.write",),
            bindings=(SecretBinding("GITHUB_TOKEN", self.reference),),
            executor=executor,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(observed, {"GITHUB_TOKEN": "super-secret-value-123"})
        self.assertEqual(self.provider.resolve_calls, ["github-prod-token"])
        self.assertFalse(hasattr(self.broker, "list"))
        self.assertFalse(hasattr(self.broker, "enumerate"))

    def test_cross_mission_access_fails_before_provider_resolution(self) -> None:
        with self.assertRaisesRegex(PermissionError, "cross_mission_secret_access_denied"):
            self.broker.execute_with_bindings(
                mission_id="MISSION-002",
                actor_id="A11",
                agent_capabilities=("github.write",),
                bindings=(SecretBinding("GITHUB_TOKEN", self.reference),),
                executor=lambda env: env,
            )
        self.assertEqual(self.provider.resolve_calls, [])

    def test_missing_capability_fails_before_provider_resolution(self) -> None:
        with self.assertRaisesRegex(PermissionError, "missing_secret_capability"):
            self.broker.execute_with_bindings(
                mission_id="MISSION-001",
                actor_id="A05",
                agent_capabilities=("frontend.write",),
                bindings=(SecretBinding("GITHUB_TOKEN", self.reference),),
                executor=lambda env: env,
            )
        self.assertEqual(self.provider.resolve_calls, [])

    def test_secret_material_never_reveals_value_via_str_or_repr(self) -> None:
        material = SecretMaterial(reference=self.reference, value="super-secret-value-123")
        self.assertEqual(str(material), REDACTED_SECRET)
        self.assertNotIn("super-secret-value-123", repr(material))
        self.assertIn("github-prod-token", repr(material))

    def test_tracer_redacts_secret_material_and_sensitive_keys(self) -> None:
        material = SecretMaterial(reference=self.reference, value="super-secret-value-123")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.db"
            tracer = SQLiteTracer(path)
            tracer.trace(
                mission_id="MISSION-001",
                actor_id="A11",
                event_name="secret-test",
                payload={
                    "lease": material,
                    "nested": {"api_key": "plaintext-api-key", "safe": "visible"},
                    "reference": self.reference,
                },
            )
            payload = tracer.events("MISSION-001")[0]["payload"]

        self.assertEqual(payload["lease"], REDACTED_SECRET)
        self.assertEqual(payload["nested"]["api_key"], REDACTED)
        self.assertEqual(payload["nested"]["safe"], "visible")
        self.assertEqual(payload["reference"]["secret_id"], "github-prod-token")
        encoded = json.dumps(payload)
        self.assertNotIn("super-secret-value-123", encoded)
        self.assertNotIn("plaintext-api-key", encoded)

    def test_evaluation_serialization_redacts_secret_material(self) -> None:
        material = SecretMaterial(reference=self.reference, value="super-secret-value-123")
        encoded = SQLiteEvaluationStore._dump({"material": material, "reference": self.reference})
        self.assertNotIn("super-secret-value-123", encoded)
        self.assertIn(REDACTED_SECRET, encoded)
        self.assertIn("github-prod-token", encoded)

    def test_secret_reference_schema_is_machine_readable_and_value_free(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "secret-reference.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("value", schema["properties"])
        self.assertNotIn("secret_value", schema["properties"])
        self.assertEqual(set(self.reference.to_dict()), set(schema["required"]))


if __name__ == "__main__":
    unittest.main()
