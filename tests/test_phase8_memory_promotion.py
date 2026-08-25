import unittest

from factory.memory import MemoryCandidate, MemoryPromotionDecision, MemoryPromotionGate


class Phase8MemoryPromotionTests(unittest.TestCase):
    def candidate(self, *, source_trust="CANONICAL", proposed_by="A06-BACKEND"):
        return MemoryCandidate(
            candidate_id="MEM-CAND-1",
            mission_id="MISSION-1",
            proposed_by=proposed_by,
            category="FAILURE",
            statement="Ambiguous external writes must reconcile before retry.",
            evidence_refs=("test://phase6/unknown-write", "event://reconciliation/1"),
            source_ref="artifact://phase6-completion",
            source_hash="sha256:source",
            source_trust=source_trust,
        )

    def decision(self, *, reviewer_id="A12-RED-TEAM", status="APPROVED", refs=None):
        return MemoryPromotionDecision(
            candidate_id="MEM-CAND-1",
            reviewer_id=reviewer_id,
            status=status,
            reason="Evidence confirms a reusable failure-prevention rule.",
            verified_evidence_refs=refs or ("test://phase6/unknown-write", "event://reconciliation/1"),
        )

    def test_reviewed_canonical_lesson_can_be_promoted(self):
        entry = MemoryPromotionGate().promote(
            candidate=self.candidate(),
            decision=self.decision(),
            memory_id="MEM-1",
        )
        self.assertEqual(entry.promoted_by, "A12-RED-TEAM")
        self.assertTrue(entry.fingerprint.startswith("sha256:"))

    def test_proposer_cannot_review_own_memory_candidate(self):
        with self.assertRaisesRegex(ValueError, "independent reviewer"):
            MemoryPromotionGate().promote(
                candidate=self.candidate(),
                decision=self.decision(reviewer_id="A06-BACKEND"),
                memory_id="MEM-1",
            )

    def test_untrusted_external_content_cannot_be_promoted_directly(self):
        with self.assertRaisesRegex(RuntimeError, "untrusted external"):
            MemoryPromotionGate().promote(
                candidate=self.candidate(source_trust="UNTRUSTED_EXTERNAL"),
                decision=self.decision(),
                memory_id="MEM-1",
            )

    def test_reviewer_must_verify_all_evidence(self):
        with self.assertRaisesRegex(ValueError, "verify all"):
            MemoryPromotionGate().promote(
                candidate=self.candidate(),
                decision=self.decision(refs=("test://phase6/unknown-write",)),
                memory_id="MEM-1",
            )

    def test_rejected_candidate_cannot_enter_memory(self):
        with self.assertRaisesRegex(RuntimeError, "rejected"):
            MemoryPromotionGate().promote(
                candidate=self.candidate(),
                decision=self.decision(status="REJECTED"),
                memory_id="MEM-1",
            )


if __name__ == "__main__":
    unittest.main()
