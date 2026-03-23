# Lessons Learned

## 2026-03-23 Security + Implementation Review

### What We Learned
- The core idea is coherent for domains with objective and reproducible metrics (performance engineering, selected ML/quant workloads).
- The MVP implementation is strong for a first version: intent declaration, benchmark diffing, guardrails, anomaly checks, and chain visualization are all in place.
- The primary deployment blocker is trust-boundary mismatch: the system describes untrusted workers, but verifier execution was previously unsandboxed.
- Production-readiness requires protocol guarantees beyond measurement logic: signed attestations, enforced permissions, and interaction/quarantine controls.

### Hardening Completed In This Pass
- Added strict schema validation for commit intent and guardrails in `verifier.py`.
- Added sandbox execution modes for benchmark/test runs in `verifier.py`:
  - `GITPROOF_SANDBOX_MODE=local|docker|custom`
  - Optional `GITPROOF_SANDBOX_DOCKER_IMAGE`
  - Optional `GITPROOF_SANDBOX_RUNNER` for VM/wrapper integration.
- Replaced `chain.json` append logic with lock + atomic write semantics.
- Removed dynamic HTML injection paths in `viewer.html` by using DOM APIs (`createElement` + `textContent`) for untrusted chain data.

### Action Item To Close Implementation Feedback
- Build and enforce a fully trusted verification envelope so "untrusted workers" is true in practice, not only in docs.
  - Deliverables:
    1. Standardized sandbox runner profile (container/VM policy, resource/network/fs limits).
    2. Commit/result attestation (sign verifier outputs and bind to commit hash).
    3. Tier-based permission enforcement in verifier path (not only in reputation reporting).
    4. Interaction/quarantine checks for cross-commit regressions before promotion.
  - Exit criteria:
    - Verifier never executes worker code on host directly in production mode.
    - Every accepted verdict is signed and traceable to immutable inputs.
    - Permission and promotion checks are enforced in code paths that gate acceptance.
