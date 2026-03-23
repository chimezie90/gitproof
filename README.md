# GitProof

**Git is already a blockchain. Here's the consensus protocol it's missing.**

A verification protocol for autonomous software improvement. Commits declare intent. Verifiers measure impact. The chain captures what worked, what didn't, and what broke.

```
WORKER → VERIFIER → STAGING → CANARY (1-5%) → PRODUCTION
           ↓           ↓          ↓
        REJECTED    DEMOTED    ROLLED BACK
```

---

## The Problem

AI agents can now autonomously explore, code, and experiment. Scale that to N agents modifying a shared codebase and you have a consensus problem: who decides which changes survive?

Code review doesn't scale to machines. CI/CD catches breakage but not degradation. What's needed is continuous metric verification — not "did the tests pass?" but "did the system get better, and did anything else get worse?"

## The Solution

Every commit declares its intent:

```yaml
---
intent:
  target_metric: bench_matrix_multiply
  target_direction: decrease
  minimum_delta: 0.15
guardrails:
  - metric: bench_prime_sieve
    constraint: "< 1.05"
---
```

The verifier checks three things:
1. **Did it hit the target?** — measure the declared metric
2. **Did it breach its guardrails?** — measure the declared risks
3. **What happened to everything else?** — anomaly-detect undeclared side effects

```
============================================================
AUTOBLOCKCHAIN VERIFIER
============================================================
Verifying commit: 680cbcdff28d

--- Target Check ---
  bench_matrix_multiply: 0.162s → 0.092s
  Actual delta: 43.2% (required: 15%)
  Target: MET ✓

--- Guardrail Check ---
  bench_prime_sieve: ratio=1.0140 < 1.05 → PASS
  bench_knapsack: ratio=1.0472 < 1.05 → PASS

--- Anomaly Detection (threshold: 10%) ---
  bench_lcs: 9.6% (slower) — OK ✓
  bench_json_parse: 0.4% (faster) — OK ✓

============================================================
VERDICT: ACCEPTED ✓
  bench_matrix_multiply improved by 43.2%
============================================================
```

## Try It

```bash
git clone https://github.com/chimezie90/gitproof
cd gitproof

# Run baseline benchmarks
python3 -m benchmarks.bench

# Create a worktree, optimize a function
python3 worker.py new --name "my-optimization"
# ... edit benchmarks/functions.py ...
# ... commit with intent declaration ...
python3 worker.py submit

# Or verify any commit directly
python3 verifier.py verify <commit-hash>

# View the chain
open viewer.html

# Check reputation leaderboard
python3 reputation.py leaderboard
```

## Real-World Validation

We used GitProof to optimize two major open source projects and submitted PRs with verification evidence:

| Project | PR | Optimization | Speedup |
|---|---|---|---|
| NetworkX | [#8579](https://github.com/networkx/networkx/pull/8579) | `has_path()` — bidirectional BFS | 1.2-2.7x |
| NetworkX | [#8580](https://github.com/networkx/networkx/pull/8580) | Directed clustering — cached neighbor sets | **5.1x** |
| SymPy | [#29499](https://github.com/sympy/sympy/pull/29499) | `subs()` — xreplace fast path | **5-20x** |
| SymPy | [#29500](https://github.com/sympy/sympy/pull/29500) | Symbolic matrix rref — DomainMatrix field path | **27-100x** |

Each PR description includes structured verification evidence: intent declaration, benchmark results, guardrails checked, anomaly detection clean. The reviewer sees exactly what was measured instead of "I think this is faster."

## Components

| File | Purpose |
|---|---|
| `benchmarks/functions.py` | 5 naive benchmark functions (optimization targets) |
| `benchmarks/tests.py` | 25 correctness tests (global health check) |
| `benchmarks/bench.py` | Deterministic benchmark runner |
| `verifier.py` | Verification protocol (target + guardrails + anomaly detection) |
| `compare_runner.py` | Fair interleaved benchmark comparison |
| `reputation.py` | Reputation system with tiers |
| `worker.py` | Worker harness (worktrees, submit, baseline) |
| `viewer.html` | Chain dashboard (DAG + charts + detail panel) |

## Reputation System

Workers earn reputation through accepted commits and lose it through rejected ones.

```
accepted commit:  +improvement_magnitude (capped at 1.0)
rejected commit:  -0.5 (flat penalty)
```

| Tier | Score | Permissions |
|---|---|---|
| Newcomer | 0.0 | Modify benchmark functions only |
| Contributor | 1.0 | Modify benchmarks/, add tests |
| Trusted | 3.0 | Modify verification thresholds |
| Core | 10.0 | Change the metric set |

```bash
python3 reputation.py leaderboard
python3 reputation.py author agent-7
python3 reputation.py check agent-7 thresholds
```

## Sandboxed Verification Mode

`verifier.py` supports sandboxed execution for untrusted benchmark code.

```bash
# Legacy/local execution (NOT for untrusted workers)
export GITPROOF_SANDBOX_MODE=local

# Container sandbox (recommended for untrusted workers; requires Docker)
export GITPROOF_SANDBOX_MODE=docker
export GITPROOF_SANDBOX_DOCKER_IMAGE=python:3.12-slim

# Custom wrapper/VM runner (runner receives the python command appended)
export GITPROOF_SANDBOX_MODE=custom
export GITPROOF_SANDBOX_RUNNER="/path/to/your-sandbox-wrapper"
```

Then run verification normally:

```bash
python3 verifier.py verify <commit-hash>
```

## How It Works

The verification protocol has four layers of defense:

1. **Global Health** — fixed metrics every commit is checked against (correctness = 100%, always)
2. **Anomaly Detection** — flag any undeclared metric that regressed more than 10%
3. **Interaction Testing** — pairwise verification catches two safe commits that are jointly catastrophic
4. **Promotion Pipeline** — staging (simulation) → canary (1-5% real users) → production

## Read the Paper

**[WHITEPAPER.md](WHITEPAPER.md)** — "Git Is Already a Blockchain. Here's the Consensus Protocol It's Missing."

Covers: the coordination problem, commits as hypotheses, the side effects problem, architecture, reputation, and proof of useful work.

## Roadmap

Execution roadmap and milestone priorities live in **[ROADMAP.md](ROADMAP.md)**.

---

*Emmanuel Chimezie / Mexkoy — March 2026*

*[@chimezie90](https://x.com/chimezie90)*
