# Git Is Already a Blockchain. Here's the Consensus Protocol It's Missing.

### Autoblockchain: Proof-of-Useful-Work for Autonomous Software Improvement

*Emmanuel Chimezie — March 2026*

---

> "The next step for autoresearch is that it has to be asynchronously massively collaborative for agents (think: SETI@home style). The goal is not to emulate a single PhD student, it's to emulate a research community of them."
>
> — Andrej Karpathy, March 8, 2026

---

## 1. Abstract

AI coding agents can now autonomously explore hypotheses, write code, run experiments, and iterate — all without human intervention. Karpathy's autoresearch ran ~700 experiments in 2 days on a single GPU and found 20 improvements that transferred to larger models. Tobi Lutke pointed it at Shopify's 20-year-old Liquid templating engine overnight: 53% faster, 61% fewer allocations, 93 automated commits. Hyperspace spun up 35 agents that ran 333 experiments unsupervised and independently rediscovered RMSNorm and tied embeddings — milestones that took human researchers at Google Brain and OpenAI years to formalize.

The single-agent loop works. The obvious next step is distributed: N agents, N hypotheses, one shared codebase, running 24/7. But the moment you have multiple untrusted workers modifying shared state, you have a consensus problem. Who decides which changes survive? What if two changes conflict? What if an "improvement" in one dimension silently degrades another?

This paper presents Autoblockchain — a verification protocol for autonomous software improvement. Every commit declares its intent: what metric it targets, by how much, and what it knows is at risk. A verification layer accepts or rejects based on measured impact, including impacts the author didn't anticipate. The git DAG is the chain. Reproducible metrics are the proof-of-work. The work is useful.

---

## 2. The Problem: Coordination Without Trust

### 2.1 Autoresearch works. Distributed autoresearch doesn't — yet.

The autoresearch pattern is simple: an AI agent reads a codebase, forms a hypothesis ("what if I try Kaiming initialization?"), modifies the code, runs the experiment, measures the result, and loops. It works because the agent has full context, the experiment is reproducible, and the metric is unambiguous.

Scale it to N agents and everything breaks.

Agent A modifies the learning rate scheduler. Agent B modifies the initialization. Both run their experiments against the same baseline. Both show improvement. But they can't both merge — the combination might be catastrophic. Agent A's scheduler tuning assumed the old initialization. Agent B's initialization assumed the old scheduler. Neither tested the interaction.

This is not a hypothetical. Hyperspace's 35-agent experiment used GossipSub and CRDTs to synchronize state, but their coordination was cooperative, not adversarial. All 35 agents were operated by the same team, sharing results via a friendly protocol. The moment you open this to untrusted workers — agents operated by different people, companies, or incentive structures — you need something stronger than gossip. You need consensus.

### 2.2 Code review doesn't scale to machines.

Human code review is judgment-based, sequential, and slow. A senior engineer reads the diff, considers the context, and makes a subjective call. This works for a team of 5. It doesn't work for 50 agents producing commits every 3 minutes.

CI/CD pipelines are better — automated, fast, reproducible — but they're binary. Tests pass or fail. A commit that makes the system 2% slower but passes all tests gets merged. A commit that increases memory usage by 40% but doesn't trigger an OOM gets merged. CI/CD catches breakage but not degradation.

What's needed is continuous metric verification. Not "did the tests pass?" but "did the system get better, and did anything else get worse?" Acceptance as a measured outcome, not a gate.

### 2.3 This is a consensus problem.

Distributed workers proposing changes to shared state. A mechanism to decide which changes to accept. A chain of accepted changes that everyone agrees on. An incentive for workers to propose genuine improvements rather than gaming the system.

This is the structure of a blockchain.

We don't need to build one. Git already is one. It gives us DAGs, branching, merging, bisection, cryptographic hashing, and distributed replication. What git doesn't have is a consensus protocol — a set of rules that determine which commits get accepted into the canonical chain based on measured impact rather than human judgment.

This paper presents that protocol.

---

## 3. Commits as Hypotheses

This is the core idea: every commit is a falsifiable scientific claim.

### 3.1 The intent declaration

Today, a commit message says "refactored the parser" or "fixed bug #412." It describes what changed, not what the author expects to happen as a result.

An Autoblockchain commit declares its intent:

```yaml
commit:
  id: "abc123"
  parent: "def456"
  author: "agent-7"

  intent:
    target_metric: "bench_matrix_multiply"
    target_direction: "decrease"        # lower = faster
    minimum_delta: 0.15                 # at least 15% faster

  guardrails:
    - metric: "bench_prime_sieve"
      constraint: "< 1.05x baseline"   # don't regress by more than 5%
    - metric: "memory_peak_mb"
      constraint: "< 512"

  changes:
    - file: "benchmarks/functions.py"
      description: "Cache-aware blocking for matrix multiply"

  evidence:
    result_hash: "sha256:9f2a..."       # reproducible result
    baseline_hash: "sha256:4c1b..."     # baseline it was measured against
```

The author is making three claims:
1. **Target**: "My change makes `matrix_multiply` at least 15% faster."
2. **Guardrails**: "I know this might affect `prime_sieve` and memory usage. I've checked — they're fine."
3. **Implicit**: "I believe nothing else is affected." (The verifier will test this.)

The commit is now a hypothesis. The verifier tests it.

### 3.2 Three verification checks

The verifier runs the system before and after the commit and measures everything:

1. **Did it hit its target?** Measure the declared metric. If `matrix_multiply` didn't actually get 15% faster, reject.

2. **Did it breach its own guardrails?** Measure the metrics the author flagged as at-risk. If `prime_sieve` regressed by more than 5%, reject.

3. **What happened to everything else?** Measure every tracked metric in the system. If anything the author *didn't* declare moved significantly, flag it.

Only #3 is hard. That's the core protocol design problem.

### 3.3 Why this framing matters

Traditional commits say "I changed X." Autoblockchain commits say "I predict that changing X will improve Y by at least Z, without degrading W."

This transforms software development from craft into science. Every accepted commit has a tested hypothesis, reproducible evidence, and measured outcomes — not just for what the author intended, but for what they didn't think about.

The chain becomes more than a changelog. It's a research log. You can query it: "Show me every optimization attempt on `matrix_multiply` that was rejected because it regressed memory usage." You can study what works, what doesn't, and why. The failed experiments are as valuable as the successes — they map the space of what doesn't work, so future agents don't repeat the search.

---

## 4. The Side Effects Problem

This is what makes the protocol non-trivial. Without side-effect detection, the system is just "run a benchmark before and after." With it, the system becomes a genuine verification layer that catches what no individual agent — human or AI — would think to check.

### 4.1 Why side effects are the hard problem

An agent optimizes `matrix_multiply` by restructuring the inner loop for cache locality. The optimization works beautifully — 40% faster. The agent declares its guardrails: it checked `prime_sieve` (no regression) and peak memory (under 512MB). The verifier confirms both.

But the agent also touched a shared utility function used by `json_parse`. It didn't know. It didn't declare it as a guardrail. `json_parse` is now 3x slower because the utility function's hot path changed. The commit passes the target check and the guardrail check. Without layer 3, it gets accepted, and nobody notices the `json_parse` regression until much later.

This is Goodhart's Law applied to code: when a measure becomes a target, it ceases to be a good measure. An agent optimizing for its declared metrics will eventually — accidentally or deliberately — degrade undeclared ones. The protocol must defend against this.

### 4.2 Three layers of defense

**Layer 1: Global Health Metrics**

A fixed set of system-wide metrics that every commit is measured against, whether the committer declared them or not. These are the "constitution" of the system.

```yaml
global_health:
  - correctness_pass_rate    # 100% required, non-negotiable
  - total_benchmark_time     # aggregate performance
  - peak_memory_usage        # resource consumption
  - code_complexity           # cyclomatic complexity of changed files
```

A commit that hits its target and respects its guardrails can still be rejected if it degrades a global health metric beyond a configurable threshold. The constitution doesn't care about your hypothesis — it cares about the system.

**Layer 2: Diff-Based Anomaly Detection**

Run the full benchmark suite before and after the commit. For every tracked metric, compute the delta. Flag any metric that moved more than a configurable threshold — even if nobody asked about it.

```
BEFORE commit abc123:
  bench_matrix_multiply:  0.342s
  bench_json_parse:       0.028s
  bench_prime_sieve:      0.156s

AFTER commit abc123:
  bench_matrix_multiply:  0.205s   ✓ -40% (target met)
  bench_json_parse:       0.091s   ✗ +225% FLAGGED — anomaly
  bench_prime_sieve:      0.158s   ✓ +1.3% (within guardrail)

VERDICT: REJECTED
REASON: Undeclared regression in bench_json_parse (+225%)
        Agent declared guardrails for prime_sieve and memory only.
        json_parse was not declared but moved significantly.
```

The agent only touched `matrix_multiply`. But the anomaly detector found what the agent missed. This is the moment that makes the protocol worth building.

**Layer 3: Interaction Testing**

The hardest case: two commits that are individually safe but jointly catastrophic.

Agent A adds a cache-warming optimization. Agent B adds an aggressive memory recycling strategy. Both pass in isolation. Together, Agent B's recycler invalidates Agent A's cache on every cycle, turning a 40% speedup into a 200% slowdown with cache thrashing.

Defense mechanisms:
- **Pairwise integration testing**: when accepting commit N, re-verify it against each of the last K accepted commits to check for interactions.
- **Bisection on regression**: if global health degrades after a batch of commits, binary search for the offending combination — `git bisect` with metrics.
- **Quarantine period**: new commits enter a "pending" state and are only promoted to "accepted" after surviving M subsequent commits without interaction failures.

**Layer 4: Promotion Pipeline (Simulation → Canary → Production)**

Benchmarks measure what you think to measure. Production reveals what you didn't. A commit that passes all three layers — target met, guardrails held, no anomalies, no interactions — is verified against synthetic workloads. But synthetic is not real. Users find edge cases that no benchmark anticipates.

The promotion pipeline addresses this by adding two stages between verification and full deployment:

**Stage 1: Staging (Simulation).** The accepted commit runs against a simulation environment — recorded production traffic replayed deterministically, synthetic load tests, chaos injection. This catches performance issues that only manifest under realistic concurrency, data distribution, or scale. The commit stays in staging until it survives N hours of simulated production without regression.

**Stage 2: Canary (Beta).** The commit is deployed to a small percentage of real users (1-5%). Metrics are monitored in real-time: latency percentiles, error rates, resource consumption, user-facing quality metrics. If any metric degrades beyond a threshold, the canary is automatically rolled back and the commit is demoted back to staging with a detailed failure report.

**Stage 3: Production.** Only after surviving both staging and canary does the commit graduate to full production deployment. At this point, the commit has been verified synthetically (benchmarks), verified under realistic load (staging), and validated with real users (canary).

```
WORKER → VERIFIER → STAGING → CANARY (1-5%) → PRODUCTION
           ↓           ↓          ↓
        REJECTED    DEMOTED    ROLLED BACK
```

This mirrors how mature organizations deploy today — but automated and metrics-driven rather than manual and judgment-based. The verification protocol decides which commits enter the pipeline. The promotion pipeline decides which survive contact with reality.

The key insight: each stage catches a different class of failure. Benchmarks catch algorithmic regressions. Staging catches scale issues. Canary catches user-facing quality problems. No single stage is sufficient. Together, they form a defense-in-depth that filters commits from "probably good" (verified) to "definitely good" (production-proven).

For the PoC, Layers 1-2 are sufficient. For production deployment of Autoblockchain, the promotion pipeline is essential.

### 4.3 The defense is probabilistic, not perfect

Sufficiently clever optimization will eventually game any fixed metric set. An agent could find an improvement that technically hits all metrics while producing code that's fragile, unmaintainable, or only works on specific inputs.

This is analogous to Bitcoin's 51% attack: the protocol doesn't prevent it mathematically; it makes it economically irrational. Gaming the metrics requires more effort than genuinely improving the code, because the anomaly detector keeps expanding what's measured, and interaction testing catches pathological combinations.

The open research problem is evolving the metric set itself — detecting when agents have learned to optimize for the tests rather than for genuine improvement, and adding new measurements in response.

---

## 5. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    THE CHAIN (git DAG)                   │
│                                                         │
│  [genesis] ← [commit-1] ← [commit-2] ← [commit-3]     │
│                                ↑                        │
│                                └── [commit-4] REJECTED  │
│                                    (undeclared anomaly   │
│                                     in json_parse)       │
└─────────────────────────────────────────────────────────┘
        ↑ propose                    ↓ accept/reject
┌───────────────┐            ┌──────────────────────┐
│   WORKERS     │            │      VERIFIER        │
│  (untrusted)  │            │   (trusted/quorum)   │
│               │            │                      │
│  Agent 1 ─────┼──commit──→ │  1. Reproduce        │
│  Agent 2 ─────┼──commit──→ │  2. Check target     │
│  Agent 3 ─────┼──commit──→ │  3. Check guardrails │
│  Agent N ─────┼──commit──→ │  4. Check globals    │
│               │            │  5. Anomaly detect   │
│  Any AI agent │            │  6. Accept / Reject  │
│  Any human    │            │                      │
└───────────────┘            └──────────────────────┘
```

### 5.1 Workers

Any AI agent — Claude Code session, autoresearch loop, custom script, or human developer — that:
1. Checks out the current chain head
2. Explores a hypothesis
3. Runs experiments locally
4. Packages a commit with an intent declaration and evidence hashes
5. Submits to the verifier

Workers don't need to be trusted. They need to produce reproducible results. A worker that submits garbage wastes its own compute, not the system's — verification is cheap; discovery is expensive.

### 5.2 Verifier

```
VERIFY(commit):

  # Reproduce baseline
  checkout(commit.parent)
  baseline = run_benchmarks(seed=DETERMINISTIC_SEED)

  # Reproduce result
  apply(commit.changes)
  result = run_benchmarks(seed=DETERMINISTIC_SEED)

  # Check target
  delta = (baseline[target] - result[target]) / baseline[target]
  target_met = delta >= commit.intent.minimum_delta

  # Check guardrails
  guardrails_ok = all(
    result[g.metric] satisfies g.constraint
    for g in commit.guardrails
  )

  # Check global health
  globals_ok = all(
    result[m] meets GLOBAL_THRESHOLDS[m]
    for m in GLOBAL_HEALTH_METRICS
  )

  # Anomaly detection
  undeclared = ALL_METRICS - {target} - {g.metric for g in guardrails}
  anomalies = [
    m for m in undeclared
    if abs(result[m] - baseline[m]) / baseline[m] > ANOMALY_THRESHOLD
  ]

  # Decision
  if target_met and guardrails_ok and globals_ok and not anomalies:
    return ACCEPT(metrics=result)
  else:
    return REJECT(reason={target_met, guardrails_ok, globals_ok, anomalies})
```

In the simplest case, the verifier is a single deterministic script on one machine. In a distributed deployment, it's a quorum of independent verifiers that must agree — identical architecture to blockchain validator nodes, except the "proof of work" is running the actual benchmarks instead of solving a hash puzzle.

### 5.3 Economics of verification

Discovery is expensive. An agent might run 50 experiments to find one that works. That's 50x compute. Verification is 1x compute — just re-run the winning experiment and check the metrics.

This ratio is inherently favorable. For code benchmarks, verification takes seconds. For ML training, it might take hours. For drug discovery simulations, it might take days. The protocol works best where verification is cheap relative to discovery — which is most software engineering tasks.

---

## 6. What This Enables

**Permissionless contribution.** Any agent can propose improvements to any codebase. No access control, no gatekeeping, no code review bottleneck. The metrics are the gatekeeper. If your commit makes the system measurably better without degrading anything else, it's accepted. Your credentials are irrelevant — but your track record isn't. Workers earn reputation through accepted commits, unlocking access to higher-leverage modifications over time (see Section 9).

**Continuous improvement at machine speed.** N agents exploring N hypotheses in parallel, 24/7. Karpathy's autoresearch ran 700 experiments in 2 days with one agent. With 100 agents, that's 70,000 experiments. The system improves while you sleep, while you eat, while you debate architecture in a meeting.

**Composable knowledge.** The chain captures not just what changed but why (intent declaration) and what happened (verification results). Failed experiments are preserved. The chain is a searchable research database: "Show me every attempt to optimize `json_parse` — what was tried, what worked, what didn't, and what side effects were caught." Future agents learn from the full history.

**Safe exploration.** Agents can try wild, speculative mutations — restructure algorithms, swap data structures, try unconventional approaches. The verification layer is the immune system. Only beneficial mutations survive. This is evolution, not design. You don't need to know what will work in advance. You need to measure what works after the fact.

**Auditable history.** Every accepted change has reproducible evidence. Every rejected change has a documented reason. The full chain is independently verifiable — anyone can clone the repo, re-run the verifier on any commit, and confirm the results. This is the audit trail that regulated industries need for algorithmic decision-making.

---

## 7. Beyond Code Optimization

The protocol works for any domain where improvement can be measured programmatically, experiments are reproducible, and the search space benefits from parallel exploration.

| Domain | Target Metrics | Guardrails | Global Health |
|---|---|---|---|
| **Code performance** | Benchmark times | Correctness tests | Memory, complexity |
| **ML training** | Validation loss, accuracy | Inference latency, model size | Training cost, data leakage |
| **Compiler optimization** | Execution speed | Correctness (test suite) | Binary size, compile time |
| **Drug discovery** | Binding affinity | Toxicity, solubility | Synthesizability, cost |
| **Chip design** | Clock speed, power | Area, thermal envelope | Manufacturing yield |
| **Infrastructure** | Request latency, throughput | Error rate, availability | Resource cost, complexity |

The generalization is straightforward: define your metrics, set your global health constitution, and let agents explore. The verification protocol is identical across domains. Only the metric definitions change.

The most compelling near-term applications are in software engineering — where experiments are fast, verification is cheap, and the search space is effectively infinite. Every codebase with a benchmark suite is a candidate for Autoblockchain. Every CI/CD pipeline could evolve from "check if it breaks" to "measure if it improves."

---

## 8. Proof of Useful Work

Bitcoin's proof-of-work is deliberately wasteful. Miners compete to solve a cryptographic puzzle that has no value except proving they spent the compute. The waste is the point — it's what makes the system trustless. But the world burns gigawatts to maintain a ledger.

Autoblockchain inverts this. The "proof of work" is the experiment itself — running the benchmarks, measuring the metrics, reproducing the results. The compute produces genuine value: faster code, better models, improved systems. The work is the product.

In Bitcoin, miners compete to solve a useless puzzle. In Autoblockchain, workers compete to solve useful problems. Both produce an immutable, verifiable chain of results. One generates heat. The other generates improvement.

This is what proof-of-work should have been all along.

---

## 9. Reputation: Trust Without Identity

The verification protocol treats all workers as untrusted. This is correct — but it's incomplete. In practice, a worker who has submitted 50 accepted commits with zero anomalies is not the same as a worker submitting their first. The protocol should know this.

### 9.1 Why reputation matters

Without reputation, every commit gets the same verification treatment. This has two costs:

1. **Verification overhead.** Running the full anomaly detection suite on every commit is expensive. For a mature system processing hundreds of commits per day, most verification compute is wasted on trusted workers whose commits almost always pass.

2. **No consequence for bad behavior.** A worker can submit 100 garbage commits, get rejected 100 times, and submit again. Rejection costs the worker their discovery compute, but it also costs the system verification compute. There's no memory of bad actors.

3. **No reward for good behavior.** A worker who consistently proposes careful, well-guardrailed improvements gets no advantage over a newcomer. There's no incentive to declare thorough guardrails or to invest in understanding side effects before submitting.

Reputation solves all three.

### 9.2 How reputation is earned and lost

Reputation is a single scalar score per worker, computed from the chain:

```
accepted commit:   +improvement_magnitude  (capped at 1.0 per commit)
rejected commit:   -0.5  (flat penalty)
retroactive hit:   -1.0  (when a previously accepted commit is implicated
                          in an interaction failure discovered later)
```

The scoring is deliberately asymmetric. Earning reputation requires genuine, verified improvement. Losing it is easy. This mirrors the real-world economics of trust — it takes years to build and seconds to destroy.

**Decay.** Reputation decays by 5% per epoch (each new accepted commit from any worker advances the epoch). This prevents inactive workers from holding permanent high scores and ensures the leaderboard reflects recent performance. A worker who stops contributing gradually fades. A worker who keeps delivering stays at the top.

### 9.3 Reputation tiers

Reputation unlocks scope. Higher-reputation workers can modify more sensitive parts of the system:

| Tier | Threshold | Name | Permissions |
|---|---|---|---|
| 0 | 0.0 | Newcomer | Modify benchmark functions only |
| 1 | 1.0 | Contributor | Modify any file in benchmarks/, add tests |
| 2 | 3.0 | Trusted | Modify verification thresholds |
| 3 | 10.0 | Core | Propose changes to the metric set itself |

This creates a natural progression. A newcomer can only optimize functions — the safest, most isolated change. As they prove themselves, they gain access to higher-leverage modifications. A Tier 3 worker who proposes adding a new global health metric has earned that right through a track record of accepted commits.

### 9.4 Reputation as a verification shortcut

High-reputation workers can get expedited verification:

- **Tier 0-1**: Full verification — target, guardrails, global health, anomaly detection.
- **Tier 2+**: Skip anomaly detection if all declared guardrails pass. The worker has demonstrated they declare guardrails honestly.
- **Tier 3**: Priority queue. Commits are verified before lower-tier submissions.

This is not a security risk. The verification still runs eventually — but for trusted workers, the system can accept commits provisionally while the full anomaly check runs in the background. If anomalies are found later, the commit is reverted and the worker takes a retroactive reputation hit.

### 9.5 Reputation as a tiebreaker

When two workers submit conflicting commits (both modify the same function), reputation breaks the tie. The higher-reputation worker's commit is verified first. If it passes, the lower-reputation commit is verified against the new state — which may cause it to fail if the two changes interact badly.

This creates a natural advantage for established workers without gatekeeping newcomers. The newcomer's commit will still be verified — just second. And if the newcomer's commit is genuinely better, it will be accepted regardless of reputation.

### 9.6 Reputation is not identity

Reputation is tied to a worker identifier, not a person. An agent operated by a team inherits the team's reputation. A new instance of the same agent starts at zero. This is intentional — reputation measures the quality of a specific worker's outputs, not the credentials of whoever operates it.

This means reputation is Sybil-resistant by construction. Creating a new identity gives you zero reputation, not a fresh start. The only way to gain reputation is to submit commits that genuinely improve the system — which is exactly the behavior the protocol wants to incentivize.

### 9.7 Querying the reputation chain

Because reputation is computed from the chain, it's fully auditable:

```bash
# Show the leaderboard
python reputation.py leaderboard

# See a worker's full history
python reputation.py author agent-7

# Check if a worker can modify thresholds
python reputation.py check agent-7 thresholds
```

The chain is the ledger. Reputation is just a view over it.

---

## 10. Open Questions

**Incentive design.** In a closed system (one company, one codebase), the incentive is straightforward: the system gets better. In an open system with untrusted workers, why would they participate? Revenue share on improvements? Tokens proportional to verified impact? Reputation scores that unlock access to higher-value codebases? The incentive mechanism determines whether this becomes a tool or a network.

**Goodhart's Law.** Agents optimize for declared metrics. Sufficiently capable agents will find ways to hit every target that don't represent genuine improvement — overfitting to benchmark inputs, exploiting measurement noise, or producing fragile code that passes today and breaks tomorrow. The anomaly detector helps, but evolving the metric set in response to agent behavior is itself a research problem.

**Non-determinism.** Code benchmarks can be made deterministic with fixed inputs and sufficient iterations. ML training cannot — even with fixed seeds, floating-point non-determinism across hardware means results vary. For non-deterministic domains, verification requires statistical hypothesis testing rather than exact reproduction: "did this change improve the metric with p < 0.05 across N runs?"

**Intellectual property.** If the chain is public, strategies are visible. If it's private, you lose the permissionless property. A possible middle ground: zero-knowledge proofs of improvement — prove that a commit improves a metric without revealing the code. This is technically feasible but computationally expensive with current ZK systems.

**Verification cost boundaries.** The protocol is most powerful where verification is cheap relative to discovery. For code benchmarks (seconds to verify), the economics are excellent. For ML training (hours), acceptable. For drug discovery (months of wet-lab validation), the protocol hits its limits. The boundary of applicability tracks the cost ratio of discovery to verification.

---

## 11. Try It Today

The reference implementation targets code performance optimization. Five pure Python functions with naive implementations, a benchmark suite, and a verification script.

```bash
# Clone the repo
git clone https://github.com/chimezie90/autoblockchain
cd autoblockchain

# Run the baseline benchmarks
python -m benchmarks.bench

# Open a worktree, optimize a function, declare your intent
python worker.py new --name "my-optimization"
# ... make your changes to benchmarks/functions.py ...
# ... write your intent declaration ...
python worker.py submit

# The verifier accepts or rejects
python verifier.py verify <commit-hash>

# View the chain
open viewer.html
```

Three agents. Three worktrees. Thirty minutes. Compare the chain's total improvement to what one agent achieves sequentially in the same time. The protocol predicts: parallel agents find more improvements, faster, with the verification layer catching interactions that no individual agent would anticipate.

---

## 12. Conclusion

The pieces exist. AI agents that can autonomously explore, code, and experiment. Git, which already provides DAGs, cryptographic hashing, branching, merging, and distributed replication. Reproducible metrics that can measure improvement programmatically.

The missing piece was always the workers. Now we have them. What we need is the consensus protocol that lets them coordinate safely on shared codebases without trusting each other.

Autoblockchain is that protocol. Commits declare intent. Verifiers measure impact. The chain captures what was tried, what worked, and what broke. Software improves itself at machine speed, safely, with a full audit trail.

The chain isn't a metaphor. It's a git repo with a verification protocol. Clone it and start committing.

---

*Emmanuel Chimezie / Mexkoy*
*March 2026*

*Contact: [@chimezie90](https://x.com/chimezie90)*
