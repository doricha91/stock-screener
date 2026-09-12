# MFU-SV2-3 Result

Status: COMPLETE, pending ChatGPT review.

Preview ordering now activates only when the explicit runbook execution contract passed through the import preview path is v3. v1/v2 retain candidate order even when an input row happens to contain a sequence. v3 uses the existing sequence-ordered trade-bearing stream. Canonical-key and trade-ID builders are unchanged.

Validation: importer suite 17 passed; Stage B suite 31 passed; changed modules compile; `git diff --check` passed. No operating data or Git history was changed.
