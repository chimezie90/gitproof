# Autoblockchain

## Software Engineering as Proof-of-Useful-Work

A protocol for distributed, verifiable, autonomous software improvement — where AI agents propose commits, declare their intent, and a verification layer accepts or rejects based on measured impact.

This is how software engineering works in the age of agentic AI: not one developer iterating, but a swarm of untrusted workers proposing improvements to a shared codebase, verified by reproducible metrics.

Inspired by [Andrej Karpathy's observation](https://x.com/kaborav) that autoresearch with untrusted workers structurally resembles a blockchain — commits instead of blocks, proof-of-useful-work instead of proof-of-work.

---

## Core Insight

Every commit is a hypothesis with declared scope:

```yaml
commit:
  id: "abc123"
  parent: "def456"
  author: "agent-7"                     # untrusted worker
  timestamp: "2026-03-21T14:00:00Z"

  intent:
    target_metric: "sharpe_agriculture"  # what I'm trying to improve
    target_direction: "increase"
    minimum_delta: 0.3                   # how much improvement I claim

  guardrails:                            # what I know is at risk
    - metric: "max_drawdown"
      constraint: "< 15%"
    - metric: "win_rate"
      constraint: "> 0.45"

  changes:
    - file: "signals/rubber_price.py"
      description: "New rubber futures signal for OKOMUOIL"

  evidence:
    backtest_hash: "sha256:9f2a..."      # reproducible result
    dataset_hash: "sha256:4c1b..."       # exact data used
```

The system verifies three things:
1. **Did it hit the target?** — measure the declared metric
2. **Did it breach its own guardrails?** — measure the declared risks
3. **What happened to everything else?** — measure global impact the author didn't think about

Only #3 is hard. That's the core protocol design problem.

---

## The Side Effects Problem

This is the central challenge. An agent optimizes for metric A but unknowingly degrades metric B that it didn't declare as a guardrail.

### Three layers of defense

**Layer 1: Global Health Metrics**

A fixed set of system-wide metrics that every commit is measured against, whether the committer declared them or not. These are the "constitution" of the system.

```yaml
global_health:
  - portfolio_sharpe          # overall risk-adjusted return
  - max_correlation           # position independence
  - sector_concentration      # diversification
  - tail_risk_99              # extreme loss exposure
  - capital_utilization       # % of capital deployed
  - signal_redundancy         # are new signals just copies of existing ones?
```

A commit that hits its target and respects its guardrails can still be rejected if it degrades a global health metric beyond a configurable threshold.

**Layer 2: Diff-Based Anomaly Detection**

Run the full system before and after the commit. Flag any metric that moved more than N standard deviations from its baseline — even if nobody asked about it.

```
BEFORE commit abc123:
  banking_drawdown: 8.2%

AFTER commit abc123:
  banking_drawdown: 14.7%   # +6.5% — FLAGGED (>2 std devs)
```

The commit author only touched agriculture signals, but banking drawdown spiked. The anomaly detector catches what humans and agents would miss.

**Layer 3: Interaction Testing (Delayed Side Effects)**

The hardest case: two commits that are individually safe but jointly catastrophic. Agent A adds a momentum signal. Agent B adds a mean-reversion signal. Both pass in isolation. Together they cancel out and generate massive churn with transaction costs eating all returns.

Defense mechanisms:
- **Pairwise integration testing**: When accepting commit N, re-run verification with each of the last K accepted commits to check for interactions
- **Bisection on regression**: If global health degrades after a batch of commits, binary search for the offending combination (like `git bisect`)
- **Quarantine period**: New commits enter a "pending" state. Only promoted to "accepted" after surviving M subsequent commits without interaction failures

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    THE CHAIN (git DAG)                   │
│                                                         │
│  [genesis] ← [commit-1] ← [commit-2] ← [commit-3]     │
│                    ↑                                    │
│                    └──── [commit-4] (rejected: broke     │
│                           global tail_risk_99)           │
└─────────────────────────────────────────────────────────┘
        ↑ propose                    ↓ accept/reject
┌───────────────┐            ┌──────────────────┐
│   WORKERS     │            │    VERIFIER       │
│               │            │                   │
│  Agent 1 ─────┼──commit──→ │  1. Reproduce     │
│  Agent 2 ─────┼──commit──→ │  2. Check target  │
│  Agent 3 ─────┼──commit──→ │  3. Check guards  │
│  ...          │            │  4. Check globals  │
│  Agent N      │            │  5. Check anomaly  │
│               │            │  6. Accept/Reject  │
│  (untrusted)  │            │  (trusted/quorum)  │
└───────────────┘            └──────────────────┘
```

### Workers (Untrusted)

Any AI agent (Claude Code session, OpenClaw agent, custom script) that:
1. Checks out the current chain head
2. Explores a hypothesis
3. Runs experiments locally
4. Packages a commit with intent declaration + evidence
5. Submits to the verifier

Workers don't need to be trusted. They need to produce reproducible results.

### Verifier (Trusted / Quorum)

The verification layer that:
1. Reproduces the experiment from the commit's evidence hashes
2. Measures target metric, guardrail metrics, and global health metrics
3. Runs anomaly detection on all tracked metrics
4. Accepts or rejects the commit
5. Appends accepted commits to the chain

In the simplest case, the verifier is a single deterministic script. In a distributed system, it's a quorum of independent verifiers who must agree.

### The Chain (Git DAG)

The commit history IS the chain. Each commit:
- References its parent (or parents, for merges)
- Contains the code changes
- Contains the intent declaration
- Contains evidence hashes for reproducibility
- Is tagged with verification results (all metrics, pass/fail)

Git gives you this for free: branching, merging, bisection, history, blame.

---

## Verification Protocol

```
VERIFY(commit):

  # Step 1: Reproduce
  checkout(commit.parent)
  baseline = run_full_system(seed=DETERMINISTIC_SEED)

  apply(commit.changes)
  result = run_full_system(seed=DETERMINISTIC_SEED)

  # Step 2: Check target
  target_met = (
    result[commit.intent.target_metric] - baseline[commit.intent.target_metric]
    >= commit.intent.minimum_delta
  )

  # Step 3: Check guardrails
  guardrails_ok = all(
    eval(f"result[g.metric] {g.constraint}")
    for g in commit.guardrails
  )

  # Step 4: Check global health
  globals_ok = all(
    result[m] >= GLOBAL_THRESHOLDS[m]
    for m in GLOBAL_HEALTH_METRICS
  )

  # Step 5: Anomaly detection
  deltas = {
    m: (result[m] - baseline[m]) / baseline_std[m]
    for m in ALL_TRACKED_METRICS
  }
  anomalies = [m for m, d in deltas.items() if abs(d) > ANOMALY_THRESHOLD]

  # Step 6: Decision
  if target_met and guardrails_ok and globals_ok and not anomalies:
    return ACCEPT
  else:
    return REJECT(reason={
      target_met, guardrails_ok, globals_ok, anomalies
    })
```

---

## How This Changes Software Engineering

Traditional software engineering: one developer (or team) iterates on a codebase sequentially. Code review is human judgment. Tests are binary pass/fail.

Agentic software engineering: N agents iterate in parallel on a shared codebase. Verification is metric-based. Acceptance is continuous, not binary.

| Concept | Traditional | Autoblockchain |
|---|---|---|
| Worker | Developer | AI agent (untrusted) |
| Proposal | Pull request | Commit with intent declaration |
| Review | Human judgment | Automated metric verification |
| Merge criteria | "LGTM" | Target hit + guardrails held + no side effects |
| Regression test | Binary pass/fail | Continuous metric monitoring + anomaly detection |
| History | Git log | Verified chain with metric evidence |
| Revert | `git revert` | Bisection on metric regression |
| Incentive | Salary | Revenue share / tokens / reputation |

### What this enables

1. **Permissionless contribution**: Anyone (any agent) can propose improvements. No gatekeeping. The metrics are the gatekeeper.

2. **Continuous improvement at machine speed**: N agents exploring N hypotheses in parallel, 24/7. The system improves while you sleep.

3. **Reproducible research**: Every accepted commit has evidence hashes. Any result can be independently verified.

4. **Composable knowledge**: The chain captures not just WHAT changed but WHY (intent declaration) and WHAT HAPPENED (verification results). This is a research log, not just a changelog.

5. **Safe exploration**: Agents can try wild mutations. The verification layer ensures only beneficial ones survive. Evolution, not design.

---

## Domains Beyond Trading

The protocol works for any domain where:
- Improvement can be measured programmatically
- Experiments are reproducible
- The search space is large enough to benefit from parallel exploration

| Domain | Target Metrics | Guardrails | Global Health |
|---|---|---|---|
| Trading strategies | Sharpe, returns | Drawdown, win rate | Portfolio correlation, tail risk |
| ML model training | Accuracy, F1 | Inference latency, model size | Training cost, data leakage |
| Compiler optimization | Execution speed | Correctness (test suite) | Binary size, compile time |
| Drug discovery | Binding affinity | Toxicity, solubility | Synthesizability, cost |
| Chip design | Clock speed, power | Area, thermal | Manufacturing yield |
| Code quality | Performance benchmarks | Test suite pass rate | Cyclomatic complexity, bundle size |

---

## MVP: Autoquant as First Domain

The first implementation uses Emmanuel's NGX Autoquant trading system.

### What exists today
- Genome engine with mutation/crossover
- Honest backtester (costs, FX, Kelly sizing)
- 278K price records for 128 stocks
- Signal framework with pluggable signals

### What to build
1. **Intent declaration format** — YAML schema for commit metadata
2. **Verification script** — deterministic backtest runner that checks target/guardrails/globals
3. **Global health dashboard** — portfolio-level metrics computed on every verification
4. **Anomaly detector** — statistical comparison of before/after metric snapshots
5. **Worker harness** — wrapper that lets a Claude Code session propose commits in the correct format
6. **Chain viewer** — simple UI showing accepted/rejected commits with metrics

### First experiment
- Spin up 3 Claude Code sessions (workers) in parallel via git worktrees
- Each explores a different signal hypothesis for 30 minutes
- Each submits a commit with intent declaration
- Verifier script accepts or rejects
- Compare: did the system find improvements faster than a single sequential session?

---

## Open Questions

1. **Incentive design**: In a truly distributed system, why would untrusted workers participate? Token rewards proportional to verified improvement? Revenue share on profitable strategies? Reputation scores?

2. **Sybil resistance**: How do you prevent an agent from submitting 10,000 trivial commits to game a reputation system? Proof-of-useful-work means the work must be genuinely useful — but "useful" is measured by the verifier, which creates a bootstrap problem.

3. **Verification cost**: Verifying is cheaper than discovering, but not free. Who pays for verification compute? How do you handle domains where verification itself is expensive (e.g., drug trials)?

4. **Metric gaming (Goodhart's Law)**: If agents optimize for declared metrics, they will eventually find ways to hit the target that don't represent genuine improvement. The anomaly detector helps, but sufficiently clever agents will game any fixed metric set. Evolving the metrics is itself a research problem.

5. **Intellectual property**: If the chain is public, anyone can see the strategies. If it's private, you lose the permissionless property. Possible middle ground: zero-knowledge proofs of improvement (prove your commit improves Sharpe without revealing the strategy).

6. **Merge conflicts**: What happens when two agents modify the same file? Traditional merge resolution doesn't work when the "reviewers" are automated metric checks. Need a protocol for concurrent modification.

7. **Non-deterministic domains**: Trading backtests can be made deterministic with fixed seeds. But what about domains where experiments have inherent randomness (ML training, A/B tests)? Need statistical verification rather than exact reproduction.

---

## Why Now

Three things converged to make this possible:

1. **Agentic AI that can code**: Claude Code, Cursor, OpenClaw — AI agents that can read codebases, form hypotheses, write code, and run experiments. The "untrusted workers" exist now.

2. **Cheap compute for verification**: Cloud GPUs and serverless compute make it feasible to re-run experiments for verification at low cost. Verification is 1x compute; discovery is Nx compute. The ratio is favorable.

3. **Git as infrastructure**: The entire chain layer already exists. Git gives you DAGs, branching, merging, bisection, cryptographic hashing, and distributed replication. You don't need to build a blockchain. You need to build a verification protocol on top of git.

The missing piece was always the workers. Now we have them.

---

*Emmanuel Chimezie / Mexkoy, March 2026*
