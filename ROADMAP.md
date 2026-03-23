# GitProof Roadmap

Last updated: March 23, 2026

## Goal
Make GitProof production-safe for untrusted workers while preserving the current MVP velocity.

## North Star
`verifier.py` can safely evaluate untrusted commits in a hardened environment, produce signed verdicts, enforce policy, and detect interaction regressions before promotion.

## Milestones

### P0 (Blockers) — Target: April 30, 2026
1. Sandbox enforcement in production mode
- Require `GITPROOF_SANDBOX_MODE` to be `docker` or `custom` when `GITPROOF_ENV=production`.
- Fail closed if sandbox runtime is unavailable.
- Add CI checks to prevent regressions to host execution in production.

2. Signed verification attestations
- Produce a signed attestation per verdict including:
  - commit hash
  - parent hash
  - verifier version
  - sandbox mode + image digest / runner identity
  - benchmark and test result hashes
- Store and verify signatures before accepting promotion.

3. Enforced permission gates in verifier
- Enforce tier/scope checks before acceptance (not just informational reporting).
- Reject out-of-scope changes with explicit reasons in verdict output.

### P1 (Safety + Integrity) — Target: June 15, 2026
1. Interaction and quarantine workflow
- Add pairwise verification against last `K` accepted commits.
- Add quarantine window before final promotion.
- Add bisection helper for identifying offending commit combinations.

2. Reproducibility hardening
- Pin runtime image digests and benchmark seeds.
- Record environment provenance in verdict metadata.
- Add deterministic replay command for independent verifier reruns.

3. Adversarial robustness testing
- Fuzz intent parser and malformed guardrails.
- Add malicious-worker test corpus (infinite loops, monkeypatching attempts, resource abuse).
- Track false accepts / false rejects in benchmarked fixtures.

### P2 (Operations + Network Readiness) — Target: August 31, 2026
1. Auditability and observability
- Structured verifier audit logs.
- Dashboard for acceptance/rejection reasons by class.
- Alerting on attestation failures and sandbox bypass attempts.

2. Multi-verifier quorum mode
- Support N verifier signatures and quorum acceptance policy.
- Add disagreement diagnostics and tie-break policy.

3. Identity and privacy policy
- Define default public metadata policy (name/handle/email).
- Add pseudonymous mode guidance for public releases.

## Exit Criteria
1. Production mode never executes worker code directly on host.
2. Every accepted verdict is signed and traceable to immutable inputs.
3. Permission rules are enforced in acceptance code paths.
4. Interaction regressions are caught before final promotion.

## Suggested Issue Labels
- `priority:p0`
- `priority:p1`
- `priority:p2`
- `area:security`
- `area:verifier`
- `area:policy`
- `area:reproducibility`
- `area:ops`

## Suggested Weekly Cadence
1. Monday: milestone planning + issue grooming.
2. Wednesday: implementation checkpoint + risk review.
3. Friday: demo, metrics, and next-week re-prioritization.
