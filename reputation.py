"""
Autoblockchain Reputation System.

Computes and manages worker reputation scores from chain.json.
Reputation is earned through accepted commits and lost through rejected ones.

Score formula:
  accepted commit:  +improvement_magnitude (capped at 1.0 per commit)
  rejected commit:  -REJECTION_PENALTY (flat)
  retroactive hit:  -RETRO_PENALTY (when a previously accepted commit is
                     later implicated in an interaction failure)

Reputation decays by DECAY_RATE per epoch (each new accepted commit advances
the epoch). This prevents inactive workers from holding permanent high scores.

Tiers:
  Tier 0 (Newcomer):    rep < 1.0   — can only modify benchmarks/functions.py
  Tier 1 (Contributor): rep >= 1.0  — can modify benchmarks/ and add new test files
  Tier 2 (Trusted):     rep >= 3.0  — can modify verification thresholds
  Tier 3 (Core):        rep >= 10.0 — can propose changes to the metric set itself
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHAIN_FILE = os.path.join(SCRIPT_DIR, "chain.json")
REP_FILE = os.path.join(SCRIPT_DIR, "reputation.json")

# Tuning constants
REJECTION_PENALTY = 0.5
RETRO_PENALTY = 1.0
DECAY_RATE = 0.05  # 5% decay per epoch
MAX_GAIN_PER_COMMIT = 1.0

TIERS = [
    (0, "Newcomer", "Can modify benchmarks/functions.py only"),
    (1.0, "Contributor", "Can modify benchmarks/ and add test files"),
    (3.0, "Trusted", "Can modify verification thresholds"),
    (10.0, "Core", "Can propose changes to the metric set"),
]


def get_tier(score):
    """Return (tier_level, tier_name, tier_description) for a score."""
    result = TIERS[0]
    for threshold, name, desc in TIERS:
        if score >= threshold:
            result = (threshold, name, desc)
    return result


def compute_reputation(chain=None):
    """Compute reputation scores from chain data. Returns dict of {author: score_info}."""
    if chain is None:
        if not os.path.exists(CHAIN_FILE):
            return {}
        with open(CHAIN_FILE, "r") as f:
            chain = json.load(f)

    authors = {}  # author -> {score, accepted, rejected, history}
    epoch = 0

    for entry in chain:
        # Extract author from intent declaration or commit metadata
        intent = entry.get("intent", {})
        # Try to get author from the commit — for the PoC, use a default
        author = intent.get("author", "unknown")

        # Also check if there's an author field at the top level
        if author == "unknown" and "author" in entry:
            author = entry["author"]

        if author not in authors:
            authors[author] = {
                "score": 0.0,
                "accepted": 0,
                "rejected": 0,
                "total_improvement": 0.0,
                "history": [],
            }

        info = authors[author]

        if entry.get("accepted"):
            # Accepted: earn reputation proportional to improvement
            delta_pct = abs(entry.get("target_delta_pct", 0))
            gain = min(delta_pct / 100.0, MAX_GAIN_PER_COMMIT)
            info["score"] += gain
            info["accepted"] += 1
            info["total_improvement"] += delta_pct
            info["history"].append({
                "commit": entry.get("commit", "?")[:12],
                "action": "accepted",
                "delta": f"+{gain:.2f}",
                "reason": f"Improved {intent.get('intent', {}).get('target_metric', '?')} by {delta_pct:.1f}%",
            })

            # Apply decay to all OTHER authors (new epoch)
            epoch += 1
            for other_author, other_info in authors.items():
                if other_author != author:
                    decay = other_info["score"] * DECAY_RATE
                    if decay > 0.001:
                        other_info["score"] = max(0, other_info["score"] - decay)

        else:
            # Rejected: lose reputation
            info["score"] = max(0, info["score"] - REJECTION_PENALTY)
            info["rejected"] += 1
            reasons = entry.get("rejection_reasons", ["Unknown"])
            info["history"].append({
                "commit": entry.get("commit", "?")[:12],
                "action": "rejected",
                "delta": f"-{REJECTION_PENALTY:.2f}",
                "reason": reasons[0] if reasons else "Unknown",
            })

    # Add tier info
    for author, info in authors.items():
        threshold, name, desc = get_tier(info["score"])
        info["tier"] = name
        info["tier_threshold"] = threshold
        info["tier_description"] = desc

    return authors


def save_reputation(authors):
    """Save reputation scores to reputation.json."""
    with open(REP_FILE, "w") as f:
        json.dump(authors, f, indent=2)


def print_leaderboard(authors):
    """Print a formatted leaderboard."""
    if not authors:
        print("No reputation data. Run the verifier on some commits first.")
        return

    sorted_authors = sorted(authors.items(), key=lambda x: x[1]["score"], reverse=True)

    print(f"\n{'='*60}")
    print(f"AUTOBLOCKCHAIN REPUTATION LEADERBOARD")
    print(f"{'='*60}")
    print(f"{'Rank':<6}{'Author':<20}{'Score':<10}{'Tier':<15}{'A/R':<8}{'Improvement':<12}")
    print(f"{'-'*60}")

    for rank, (author, info) in enumerate(sorted_authors, 1):
        score = info["score"]
        tier = info["tier"]
        ar = f"{info['accepted']}/{info['rejected']}"
        improvement = f"{info['total_improvement']:.1f}%"
        print(f"{rank:<6}{author:<20}{score:<10.2f}{tier:<15}{ar:<8}{improvement:<12}")

    print(f"{'='*60}")

    # Print tier legend
    print(f"\nTier Levels:")
    for threshold, name, desc in TIERS:
        marker = ""
        print(f"  {name:<15} (>= {threshold:>5.1f})  {desc}")

    print()


def print_author_detail(authors, author):
    """Print detailed history for a specific author."""
    if author not in authors:
        print(f"Author '{author}' not found.")
        return

    info = authors[author]
    print(f"\n{'='*60}")
    print(f"AUTHOR: {author}")
    print(f"{'='*60}")
    print(f"  Score:       {info['score']:.2f}")
    print(f"  Tier:        {info['tier']} ({info['tier_description']})")
    print(f"  Accepted:    {info['accepted']}")
    print(f"  Rejected:    {info['rejected']}")
    print(f"  Improvement: {info['total_improvement']:.1f}% total")
    print(f"\n  History:")
    for h in info["history"]:
        status = "ACCEPTED" if h["action"] == "accepted" else "REJECTED"
        print(f"    {h['commit']}  {status:<10} {h['delta']:<8} {h['reason']}")
    print(f"{'='*60}\n")


def check_permission(authors, author, scope):
    """Check if an author has permission for a given scope.

    Scopes:
      'functions'    — modify benchmarks/functions.py (Tier 0+)
      'benchmarks'   — modify any file in benchmarks/ (Tier 1+)
      'thresholds'   — modify verification thresholds (Tier 2+)
      'metrics'      — change the metric set (Tier 3+)
    """
    scope_tiers = {
        "functions": 0,
        "benchmarks": 1.0,
        "thresholds": 3.0,
        "metrics": 10.0,
    }

    required = scope_tiers.get(scope, 0)
    score = authors.get(author, {}).get("score", 0)

    if score >= required:
        return True, f"Author '{author}' (score {score:.2f}) has permission for '{scope}' (requires {required})"
    else:
        _, tier_name, _ = get_tier(required)
        return False, f"Author '{author}' (score {score:.2f}) lacks permission for '{scope}' (requires {required}, tier {tier_name})"


def main():
    if len(sys.argv) < 2:
        print("Autoblockchain Reputation System")
        print()
        print("Commands:")
        print("  leaderboard              Show reputation leaderboard")
        print("  author <name>            Show detailed history for an author")
        print("  check <author> <scope>   Check if author has permission for scope")
        print("  refresh                  Recompute from chain.json and save")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "leaderboard":
        authors = compute_reputation()
        print_leaderboard(authors)
        save_reputation(authors)

    elif cmd == "author":
        if len(sys.argv) < 3:
            print("Usage: python reputation.py author <name>")
            sys.exit(1)
        authors = compute_reputation()
        print_author_detail(authors, sys.argv[2])

    elif cmd == "check":
        if len(sys.argv) < 4:
            print("Usage: python reputation.py check <author> <scope>")
            print("Scopes: functions, benchmarks, thresholds, metrics")
            sys.exit(1)
        authors = compute_reputation()
        ok, msg = check_permission(authors, sys.argv[2], sys.argv[3])
        print(msg)
        sys.exit(0 if ok else 1)

    elif cmd == "refresh":
        authors = compute_reputation()
        save_reputation(authors)
        print(f"Reputation data refreshed from chain.json")
        print_leaderboard(authors)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
