# Phase 10-H Research — Localization & Market Adapters

**Status:** Evidence review completed; implementation follow-ups remain  
**Research Pod roles:** R01 Planner, R02 Source Scout, R03 Evidence Verifier, R04 Contradiction Analyst  
**Scope:** Standards and runtime constraints relevant to Persian/English localization without creating a second domain model.

## Sources reviewed

1. **Unicode CLDR — Persian number formats**  
   https://www.unicode.org/cldr/charts/49/verify/numbers/fa.html  
   Finding: Persian (`fa`) uses `arabext` as the default numbering system while Latin digits are also represented as a supported numbering system.

2. **W3C — Strings on the Web: Language and Direction Metadata (2026 working draft)**  
   https://www.w3.org/TR/string-meta/  
   Finding: natural-language strings need language/direction metadata to survive processing and display correctly. Direction should be explicit when known rather than relying only on heuristics.

3. **RFC 5646 / BCP 47 — Tags for Identifying Languages**  
   https://www.rfc-editor.org/info/rfc5646/  
   Finding: language identifiers should use the BCP 47 language-tag model.

4. **Python `zoneinfo` documentation**  
   https://docs.python.org/3/library/zoneinfo.html  
   Finding: `zoneinfo` is the standard IANA-timezone interface. It uses system timezone data where available and can fall back to the first-party `tzdata` package; some systems, notably Windows, may not provide an IANA database by default.

## Verified architecture conclusions

### PASS — locale is presentation, not domain authority

The current Phase 10-H direction is correct: locale adapters may change formatting/copy, but must not change canonical price values, listing lifecycle, trust status, rights basis, search meaning or canonical route identity.

### PASS — Persian numbering profile

`fa-IR` using `arabext` digits is consistent with CLDR. The implementation also preserves the underlying numeric value rather than converting it to localized digits in canonical state.

### PASS — explicit timezone conversion

Timezone-aware canonical datetimes plus an explicit IANA target timezone are preferable to assuming a timezone from language or market location.

### PASS — currency must remain explicit

Currency is a domain/accounting fact and must not be inferred from `fa-IR`, `en-US`, city or country presentation. Localization may format a currency that is already known; it must not invent or silently convert one.

## Hidden issues discovered

### H1 — locale-level direction is not enough for user-generated strings

Current localized projections expose a global `direction` derived from the UI locale. That is useful for page/container layout, but it does not fully describe mixed-language user content.

Example: an English property title can appear inside a Persian RTL page, or Persian text can appear inside an English LTR page. W3C guidance treats direction as metadata for the string/content itself, not simply as a property of the UI language.

**Recommended follow-up:** introduce bounded string-level language/direction metadata for user/publisher content (`title`, free-text description, locality labels where appropriate), while retaining locale-level direction for layout. Do not mutate the canonical text.

### H2 — `price_minor` / `minor_value` semantics are ambiguous

The current domain field is named `price_minor`, and the localization formatter argument is named `minor_value`, but formatting currently renders the integer directly as whole currency units. This is harmless for zero-decimal currencies if the canonical amount is already in base units, but ambiguous for currencies with fractional minor units.

**Recommended follow-up:** define one canonical money contract explicitly. Either:

- store integer atomic/minor units together with a currency exponent and format accordingly, or
- rename the field to state that the integer is already a whole/base display unit.

Do not allow locale code to guess the exponent.

### H3 — cross-platform timezone database availability must be observable

`ZoneInfo` can fail when no IANA database is available. The current adapter correctly rejects unknown zones, but a production runtime should make timezone-data availability an environment capability rather than discovering the problem only when a user request reaches localization.

**Recommended follow-up:** add startup/runtime capability validation and, if cross-platform packaging requires it, pin the first-party `tzdata` dependency or provide an equivalent verified source.

### H4 — broader locale expansion should not hard-code assumptions into domain logic

The current two-profile `fa-IR` / `en-US` baseline is acceptable for Phase 10-H qualification. Future locale expansion should validate explicit profiles and use BCP 47-compatible identifiers rather than letting domain code infer script, currency or timezone from a language tag.

## Decision

**Research verdict: CONDITIONAL PASS.**

The current Phase 10-H architecture is directionally sound and its protected semantic-invariance model should be retained. Before declaring the mission localization layer production-grade, address H1–H3 and prove them with executable tests.

## Research-to-code boundary

This document is evidence input, not canonical policy by itself. Implementation changes still require normal code review/test/evidence gates. The Research Pod cannot promote these findings directly into protected organizational memory or bypass the current Mission 001 roadmap.
