# Phase 10-H Completion — Localization & Market Adapters

**Status:** PASS  
**Qualified head:** `e3082e78cd50bd5e3ba84313786fad45587b4b29`  
**GitHub Actions run:** `32856380992` — SUCCESS

## Scope qualified

Phase 10-H establishes localization as a presentation-only boundary. Locale and market adapters may change representation, but they may not mutate canonical listing meaning, lifecycle, trust, rights, route identity, search semantics or SEO authority.

Qualified capabilities:

- typed `LocaleContext` with explicit locale, language, numbering system, text direction, timezone and currency metadata;
- Persian `fa-IR` RTL and English `en-US` LTR profiles;
- deterministic message catalog keyed by qualified message/status codes;
- observable deterministic fallback for unknown message codes;
- timezone-aware date/time formatting with rejection of naive timestamps;
- localized number and unit rendering while preserving canonical numeric values;
- canonical public URL and route identity preserved across locales;
- discovery/SEO authority fields copied from qualified discovery state rather than re-decided by localization code;
- machine-readable locale, localized-consumer and localized-discovery schemas;
- package-level exports for the localization contracts.

## Critical defect found and corrected during qualification

The initial adapter could render the same numeric `price_minor` under a different currency label merely by changing `LocaleContext.currency_code`. That would have allowed a representation layer to imply a currency conversion that never occurred.

The adapter now fails closed:

- amount formatting requires an explicit `currency_code`;
- the canonical amount currency must match the requested display currency;
- currency conversion is explicitly outside the localization boundary;
- mismatched currency is rejected instead of relabelled.

This preserves the rule that localization may format a canonical economic value but may not manufacture a new one.

## Verification evidence

`tests/test_phase10_localization.py` covers:

- Persian digits and RTL metadata;
- English LTR rendering;
- explicit timezone conversion;
- explicit currency handling;
- rejection of currency relabelling;
- deterministic unknown-message fallback;
- invalid locale-profile rejection;
- semantic invariance across localized consumer projections;
- canonical URL, route, indexability, robots, noindex reasons, lastmod and structured-data invariance across localized discovery projections;
- existence and protected shape of machine-readable localization schemas.

The repository-wide test workflow succeeded on the qualified head.

## Non-goals preserved

Phase 10-H does not implement or claim:

- foreign-exchange conversion;
- locale-dependent canonical routes;
- independent localized SEO authority;
- machine translation of unreviewed content;
- identity, trust or fraud decisions;
- production deployment.

## Exit decision

Phase 10-H satisfies its bounded localization objective. The next Mission 001 milestone is **Phase 10-I — Domain assurance and bounded full-stack qualification**.
