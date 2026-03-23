"""
Autoblockchain Worker Harness.

Commands:
  python worker.py new --name "my-opt"  — create a git worktree for working
  python worker.py submit               — validate intent, run verifier, report
  python worker.py baseline             — show current baseline benchmarks
"""

import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WORKTREES_DIR = os.path.join(REPO_ROOT, ".worktrees")


def cmd_new(args):
    """Create a new worktree for an optimization attempt."""
    name = None
    for i, arg in enumerate(args):
        if arg == "--name" and i + 1 < len(args):
            name = args[i + 1]
    if not name:
        print("Usage: python worker.py new --name <name>")
        print("Example: python worker.py new --name matrix-cache-blocking")
        sys.exit(1)

    # Sanitize name
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
    branch_name = f"worker/{safe_name}"
    worktree_path = os.path.join(WORKTREES_DIR, safe_name)

    if os.path.exists(worktree_path):
        print(f"Worktree already exists: {worktree_path}")
        print(f"To remove: git worktree remove {worktree_path}")
        sys.exit(1)

    os.makedirs(WORKTREES_DIR, exist_ok=True)

    # Create branch and worktree
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT
    ).stdout.strip()

    subprocess.run(
        ["git", "worktree", "add", "-b", branch_name, worktree_path, head],
        check=True, cwd=REPO_ROOT
    )

    print(f"\nWorktree created!")
    print(f"  Path:   {worktree_path}")
    print(f"  Branch: {branch_name}")
    print(f"  Base:   {head[:12]}")
    print(f"\nNext steps:")
    print(f"  1. cd {worktree_path}")
    print(f"  2. Edit benchmarks/functions.py — optimize a function")
    print(f"  3. Commit with intent declaration:")
    print(f"     git commit -am \"$(cat <<'EOF'")
    print(f"     ---")
    print(f"     intent:")
    print(f"       target_metric: bench_matrix_multiply")
    print(f"       target_direction: decrease")
    print(f"       minimum_delta: 0.15")
    print(f"     guardrails:")
    print(f"       - metric: bench_prime_sieve")
    print(f"         constraint: \"< 1.05\"")
    print(f"     ---")
    print(f"")
    print(f"     Cache-aware blocking for matrix multiply")
    print(f"     EOF")
    print(f"     )\"")
    print(f"  4. python worker.py submit  (from this worktree)")


def cmd_submit(args):
    """Validate the latest commit's intent and run the verifier."""
    # Get the latest commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=os.getcwd()
    )
    if result.returncode != 0:
        print("Error: not in a git repository")
        sys.exit(1)
    commit_hash = result.stdout.strip()

    # Get commit message and validate it has intent
    msg_result = subprocess.run(
        ["git", "log", "-1", "--format=%B", commit_hash],
        capture_output=True, text=True, cwd=os.getcwd()
    )
    msg = msg_result.stdout

    if "---" not in msg:
        print("Error: commit message has no intent declaration (YAML frontmatter between --- markers)")
        print("\nYour commit message should look like:")
        print("  ---")
        print("  intent:")
        print("    target_metric: bench_matrix_multiply")
        print("    target_direction: decrease")
        print("    minimum_delta: 0.15")
        print("  ---")
        print("  Your description here")
        sys.exit(1)

    print(f"Submitting commit {commit_hash[:12]} for verification...")
    print()

    # Run the verifier from the main repo
    verifier_path = os.path.join(REPO_ROOT, "verifier.py")
    result = subprocess.run(
        [sys.executable, verifier_path, "verify", commit_hash],
        cwd=REPO_ROOT
    )

    sys.exit(result.returncode)


def cmd_baseline(args):
    """Show current baseline benchmark results."""
    print("Running baseline benchmarks...")
    result = subprocess.run(
        [sys.executable, "-m", "benchmarks.bench"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        print(f"Error running benchmarks: {result.stderr}")
        sys.exit(1)

    benchmarks = json.loads(result.stdout)
    print("\nCurrent baseline:")
    for name, value in sorted(benchmarks.items()):
        print(f"  {name}: {value:.6f}s")
    print("\nThese are the metrics your optimization will be measured against.")


def cmd_list(args):
    """List active worktrees."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )
    print("Active worktrees:")
    current = {}
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            current = {"path": line.split(" ", 1)[1]}
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]
        elif line == "":
            if current and current.get("path"):
                branch = current.get("branch", "detached")
                print(f"  {current['path']} ({branch})")
            current = {}


def main():
    if len(sys.argv) < 2:
        print("Autoblockchain Worker Harness")
        print()
        print("Commands:")
        print("  new --name <name>   Create a worktree for a new optimization")
        print("  submit              Submit the current commit for verification")
        print("  baseline            Show current baseline benchmarks")
        print("  list                List active worktrees")
        sys.exit(0)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "new":
        cmd_new(rest)
    elif cmd == "submit":
        cmd_submit(rest)
    elif cmd == "baseline":
        cmd_baseline(rest)
    elif cmd == "list":
        cmd_list(rest)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
