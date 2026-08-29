from __future__ import annotations

from datetime import datetime, timezone
import unittest

from factory.research_pod import (
    ClaimDisposition,
    EvidenceLink,
    EvidenceStance,
    ResearchBundle,
    ResearchClaim,
    ResearchPolicy,
    ResearchQuestion,
    ResearchVerifier,
    SourceClass,
    SourceRecord,
    sha256_text,
)


NOW = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)


def source(
    source_id: str,
    uri: str,
    publisher: str,
    source_class: SourceClass,
    independent_group: str,
    *,
    retrieved_at: str = "2026-08-29T20:00:00+00:00",
) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        uri=uri,
        title=source_id,
        publisher=publisher,
        source_class=source_class,
        independent_group=independent_group,
        retrieved_at=retrieved_at,
        content_hash=sha256_text(f"controlled fixture for {source_id}"),
    )


class ResearchPodTests(unittest.TestCase):
    def test_phase10h_research_bundle_passes_with_traced_high_authority_evidence(self) -> None:
        sources = (
            source(
                "CLDR-FA-NUMBERS",
                "https://www.unicode.org/cldr/charts/49/verify/numbers/fa.html",
                "Unicode Consortium",
                SourceClass.PRIMARY_STANDARD,
                "unicode-cldr",
            ),
            source(
                "W3C-STRING-META",
                "https://www.w3.org/TR/string-meta/",
                "W3C",
                SourceClass.PRIMARY_STANDARD,
                "w3c-i18n",
            ),
            source(
                "RFC-5646",
                "https://www.rfc-editor.org/info/rfc5646/",
                "RFC Editor",
                SourceClass.PRIMARY_STANDARD,
                "ietf-bcp47",
            ),
            source(
                "PYTHON-ZONEINFO",
                "https://docs.python.org/3/library/zoneinfo.html",
                "Python Software Foundation",
                SourceClass.OFFICIAL_DOCUMENTATION,
                "python-docs",
            ),
        )
        claims = (
            ResearchClaim(
                claim_id="C1",
                statement="Persian locale formatting may use arabext digits and must keep numeric semantics unchanged.",
                evidence=(
                    EvidenceLink("CLDR-FA-NUMBERS", EvidenceStance.SUPPORTS, "default numbering system: arabext"),
                ),
                disposition=ClaimDisposition.SUPPORTED,
                confidence=0.99,
                critical=True,
            ),
            ResearchClaim(
                claim_id="C2",
                statement="Language and base direction should be carried explicitly instead of relying on text heuristics.",
                evidence=(
                    EvidenceLink("W3C-STRING-META", EvidenceStance.SUPPORTS, "language/direction metadata guidance"),
                    EvidenceLink("RFC-5646", EvidenceStance.CONTEXT_ONLY, "BCP 47 language tags"),
                ),
                disposition=ClaimDisposition.SUPPORTED,
                confidence=0.98,
                critical=True,
            ),
            ResearchClaim(
                claim_id="C3",
                statement="Timezone localization should use explicit IANA zone identifiers and timezone-aware datetimes.",
                evidence=(
                    EvidenceLink("PYTHON-ZONEINFO", EvidenceStance.SUPPORTS, "IANA timezone support"),
                    EvidenceLink("W3C-STRING-META", EvidenceStance.CONTEXT_ONLY, "metadata must survive downstream processing"),
                ),
                disposition=ClaimDisposition.SUPPORTED,
                confidence=0.95,
                critical=False,
            ),
        )
        bundle = ResearchBundle(
            bundle_id="RB-PHASE10H-001",
            question=ResearchQuestion(
                "RQ-PHASE10H",
                "Which standards should constrain Persian/English localization adapters?",
                critical=True,
                freshness_days=60,
            ),
            sources=sources,
            claims=claims,
            conclusion="Keep locale as a presentation adapter: explicit language/direction, explicit currency, CLDR-compatible numbering, and timezone-aware conversion.",
            unresolved_gaps=("Full CLDR plural/message formatting remains outside the current dependency-free baseline.",),
            participating_agents=("R01-PLANNER", "R02-SOURCE-SCOUT", "R03-EVIDENCE-VERIFIER", "R04-CONTRADICTION-ANALYST"),
            created_at="2026-08-29T21:00:00+00:00",
        )

        assessment = ResearchVerifier().assess(bundle, now=NOW)
        self.assertTrue(assessment.accepted, assessment.issues)
        self.assertEqual(assessment.supported_claims, 3)
        self.assertGreaterEqual(assessment.high_authority_source_count, 4)
        self.assertEqual(len(bundle.fingerprint()), 71)

    def test_critical_claim_rejects_fake_independence(self) -> None:
        s1 = source("S1", "https://example.test/a", "Example", SourceClass.SECONDARY, "same-origin")
        s2 = source("S2", "https://mirror.example.test/a", "Mirror", SourceClass.SECONDARY, "same-origin")
        claim = ResearchClaim(
            "C1",
            "A high-impact architecture claim",
            (
                EvidenceLink("S1", EvidenceStance.SUPPORTS, "a"),
                EvidenceLink("S2", EvidenceStance.SUPPORTS, "b"),
            ),
            ClaimDisposition.SUPPORTED,
            0.9,
            critical=True,
        )
        bundle = ResearchBundle(
            "RB1",
            ResearchQuestion("RQ1", "critical", critical=True),
            (s1, s2),
            (claim,),
            "conclusion",
            (),
            ("R02-SOURCE-SCOUT", "R03-EVIDENCE-VERIFIER"),
            "2026-08-29T21:00:00+00:00",
        )
        assessment = ResearchVerifier().assess(bundle, now=NOW)
        self.assertFalse(assessment.accepted)
        codes = {issue.code for issue in assessment.issues}
        self.assertIn("CRITICAL_EVIDENCE_NOT_INDEPENDENT", codes)
        self.assertIn("CRITICAL_CLAIM_LOW_AUTHORITY", codes)

    def test_contradiction_cannot_be_hidden_inside_supported_claim(self) -> None:
        s1 = source("S1", "https://standards.example/a", "Standards", SourceClass.PRIMARY_STANDARD, "standard-a")
        s2 = source("S2", "https://official.example/b", "Official", SourceClass.OFFICIAL_DOCUMENTATION, "official-b")
        claim = ResearchClaim(
            "C1",
            "Claim with conflicting evidence",
            (
                EvidenceLink("S1", EvidenceStance.SUPPORTS, "support"),
                EvidenceLink("S2", EvidenceStance.CONTRADICTS, "conflict"),
            ),
            ClaimDisposition.SUPPORTED,
            0.8,
        )
        bundle = ResearchBundle(
            "RB2",
            ResearchQuestion("RQ2", "conflict handling"),
            (s1, s2),
            (claim,),
            "conclusion",
            (),
            ("R03-EVIDENCE-VERIFIER", "R04-CONTRADICTION-ANALYST"),
            "2026-08-29T21:00:00+00:00",
        )
        assessment = ResearchVerifier().assess(bundle, now=NOW)
        self.assertFalse(assessment.accepted)
        self.assertIn("CONTRADICTION_NOT_REFLECTED", {issue.code for issue in assessment.issues})

    def test_stale_evidence_fails_a_freshness_bounded_question(self) -> None:
        old = source(
            "S1",
            "https://official.example/old",
            "Official",
            SourceClass.OFFICIAL_DOCUMENTATION,
            "official",
            retrieved_at="2025-01-01T00:00:00+00:00",
        )
        claim = ResearchClaim(
            "C1",
            "Current behavior",
            (EvidenceLink("S1", EvidenceStance.SUPPORTS, "old evidence"),),
            ClaimDisposition.SUPPORTED,
            0.9,
        )
        bundle = ResearchBundle(
            "RB3",
            ResearchQuestion("RQ3", "current behavior", freshness_days=30),
            (old,),
            (claim,),
            "conclusion",
            (),
            ("R02-SOURCE-SCOUT", "R03-EVIDENCE-VERIFIER"),
            "2026-08-29T21:00:00+00:00",
        )
        assessment = ResearchVerifier().assess(bundle, now=NOW)
        self.assertFalse(assessment.accepted)
        self.assertIn("FRESHNESS_REQUIREMENT_MISSED", {issue.code for issue in assessment.issues})

    def test_insufficient_claim_cannot_be_overconfident(self) -> None:
        s1 = source("S1", "https://community.example/post", "Community", SourceClass.COMMUNITY, "community")
        claim = ResearchClaim(
            "C1",
            "Weakly evidenced observation",
            (EvidenceLink("S1", EvidenceStance.CONTEXT_ONLY, "discussion"),),
            ClaimDisposition.INSUFFICIENT,
            0.95,
        )
        bundle = ResearchBundle(
            "RB4",
            ResearchQuestion("RQ4", "weak evidence"),
            (s1,),
            (claim,),
            "No reliable conclusion yet.",
            ("Need primary evidence",),
            ("R02-SOURCE-SCOUT", "R03-EVIDENCE-VERIFIER"),
            "2026-08-29T21:00:00+00:00",
        )
        assessment = ResearchVerifier().assess(bundle, now=NOW)
        self.assertTrue(assessment.accepted)
        self.assertIn("INSUFFICIENT_OVERCONFIDENT", {issue.code for issue in assessment.issues})


if __name__ == "__main__":
    unittest.main()
