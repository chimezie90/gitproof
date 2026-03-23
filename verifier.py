"""
Autoblockchain Verifier — the verification protocol.

Parses intent from commit message YAML frontmatter, runs benchmarks before/after,
checks target, guardrails, global health, and anomaly-detects side effects.
Writes results to chain.json. Exit 0 = accepted, exit 1 = rejected.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHAIN_FILE = os.path.join(SCRIPT_DIR, "chain.json")
CHAIN_LOCK_FILE = f"{CHAIN_FILE}.lock"
ANOMALY_THRESHOLD = 0.10  # 10% undeclared movement = flagged
TARGET_DIRECTIONS = {"increase", "decrease"}
METRIC_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")
CONSTRAINT_RE = re.compile(r"^(<=|<|>=|>)\s*([0-9]+(?:\.[0-9]+)?)$")

def _get_git_root():
    """Find the actual git repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, cwd=SCRIPT_DIR
    )
    return result.stdout.strip()

def _get_subdir():
    """Get the subdirectory path of SCRIPT_DIR relative to git root."""
    git_root = _get_git_root()
    return os.path.relpath(SCRIPT_DIR, git_root)

REPO_ROOT = None  # Lazy — set on first use

def _repo_root():
    global REPO_ROOT
    if REPO_ROOT is None:
        REPO_ROOT = _get_git_root()
    return REPO_ROOT


def _execution_config():
    """Execution mode for running untrusted benchmark code."""
    mode = os.environ.get("GITPROOF_SANDBOX_MODE", "local").strip().lower() or "local"
    return {
        "mode": mode,
        "docker_image": os.environ.get("GITPROOF_SANDBOX_DOCKER_IMAGE", "python:3.12-slim").strip(),
        "custom_runner": os.environ.get("GITPROOF_SANDBOX_RUNNER", "").strip(),
    }


def _run_python(py_args, workdir, timeout):
    """Run Python code either locally or inside a sandbox runner."""
    config = _execution_config()
    mode = config["mode"]

    if mode == "local":
        cmd = [sys.executable] + py_args
        cwd = workdir
    elif mode == "docker":
        if shutil.which("docker") is None:
            raise RuntimeError("Sandbox mode 'docker' requested but docker is not installed.")
        image = config["docker_image"] or "python:3.12-slim"
        host_dir = os.path.abspath(workdir)
        container_dir = "/workspace"
        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "256",
            "--memory", "1g",
            "--cpus", "1.0",
            "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{host_dir}:{container_dir}:ro",
            "-w", container_dir,
            image,
            "python3",
        ] + py_args
        cwd = None
    elif mode == "custom":
        runner = config["custom_runner"]
        if not runner:
            raise RuntimeError(
                "Sandbox mode 'custom' requested but GITPROOF_SANDBOX_RUNNER is not set."
            )
        cmd = shlex.split(runner) + [sys.executable] + py_args
        cwd = workdir
    else:
        raise RuntimeError(
            f"Unknown sandbox mode '{mode}'. Use one of: local, docker, custom."
        )

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=timeout,
    )


def parse_yaml_frontmatter(commit_msg):
    """Extract YAML frontmatter between --- markers from commit message.
    Simple parser — no PyYAML dependency."""
    lines = commit_msg.strip().split("\n")
    if not lines or lines[0].strip() != "---":
        return None

    yaml_lines = []
    end_found = False
    for line in lines[1:]:
        if line.strip() == "---":
            end_found = True
            break
        yaml_lines.append(line)

    if not end_found:
        return None

    return parse_simple_yaml("\n".join(yaml_lines))


def parse_simple_yaml(text):
    """Minimal indent-aware YAML parser for intent declarations.
    Handles nested dicts, lists of dicts, and scalar values."""
    lines = []
    for line in text.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        lines.append(line)

    def get_indent(line):
        return len(line) - len(line.lstrip())

    def parse_block(lines, start, base_indent):
        """Parse a block of YAML at a given indent level. Returns (dict, next_index)."""
        result = {}
        i = start
        while i < len(lines):
            line = lines[i]
            indent = get_indent(line)
            if indent < base_indent:
                break
            if indent > base_indent:
                i += 1
                continue

            stripped = line.strip()

            # List item
            if stripped.startswith("- "):
                break  # handled by parent

            # Key: value
            if ":" in stripped:
                key, val = stripped.split(":", 1)
                key = key.strip()
                val = val.strip()
                if val:
                    result[key] = parse_yaml_value(val)
                    i += 1
                else:
                    # Check what's next: nested dict or list
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        next_indent = get_indent(next_line)
                        next_stripped = next_line.strip()
                        if next_indent > base_indent and next_stripped.startswith("- "):
                            # Parse list
                            lst, i = parse_list(lines, i + 1, next_indent)
                            result[key] = lst
                        elif next_indent > base_indent:
                            # Parse nested dict
                            nested, i = parse_block(lines, i + 1, next_indent)
                            result[key] = nested
                        else:
                            result[key] = None
                            i += 1
                    else:
                        result[key] = None
                        i += 1
            else:
                i += 1

        return result, i

    def parse_list(lines, start, base_indent):
        """Parse a YAML list at a given indent level. Returns (list, next_index)."""
        result = []
        i = start
        while i < len(lines):
            line = lines[i]
            indent = get_indent(line)
            if indent < base_indent:
                break

            stripped = line.strip()
            if not stripped.startswith("- "):
                # Could be continuation of previous list item
                if indent > base_indent:
                    # Additional key for the last dict item
                    if result and isinstance(result[-1], dict) and ":" in stripped:
                        key, val = stripped.split(":", 1)
                        result[-1][key.strip()] = parse_yaml_value(val.strip())
                    i += 1
                    continue
                break

            item_content = stripped[2:].strip()
            if ":" in item_content:
                # Dict item — parse first key, then look for more
                key, val = item_content.split(":", 1)
                item_dict = {key.strip(): parse_yaml_value(val.strip())}
                # Check for additional keys on following lines
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_indent = get_indent(next_line)
                    next_stripped = next_line.strip()
                    if next_indent <= base_indent:
                        break
                    if next_stripped.startswith("- "):
                        break
                    if ":" in next_stripped:
                        k2, v2 = next_stripped.split(":", 1)
                        item_dict[k2.strip()] = parse_yaml_value(v2.strip())
                    i += 1
                result.append(item_dict)
            else:
                result.append(parse_yaml_value(item_content))
                i += 1

        return result, i

    result, _ = parse_block(lines, 0, 0)
    return result


def parse_yaml_value(s):
    """Parse a YAML scalar value."""
    if not s:
        return None
    # Remove quotes
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if s == "true":
        return True
    if s == "false":
        return False
    if s == "null":
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _clean_metric_name(value):
    if not isinstance(value, str):
        return None
    metric = value.strip()
    if not metric or not METRIC_NAME_RE.fullmatch(metric):
        return None
    return metric


def _parse_minimum_delta(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0.01:
        return None
    return parsed


def _clean_constraint(value):
    if not isinstance(value, str):
        return None
    compact = " ".join(value.strip().split())
    if not CONSTRAINT_RE.fullmatch(compact):
        return None
    return compact


def validate_intent_schema(intent_data):
    """Strict schema validation for commit intent frontmatter."""
    if not isinstance(intent_data, dict):
        return None, "Intent frontmatter must be a YAML object."

    intent = intent_data.get("intent")
    if not isinstance(intent, dict):
        return None, "Field 'intent' must be a YAML object."

    target_metric = _clean_metric_name(intent.get("target_metric"))
    if not target_metric:
        return None, (
            "Field 'intent.target_metric' must be a non-empty metric name "
            "(letters, numbers, _, ., -)."
        )

    target_direction = intent.get("target_direction")
    if target_direction not in TARGET_DIRECTIONS:
        return None, "Field 'intent.target_direction' must be one of: increase, decrease."

    minimum_delta = _parse_minimum_delta(intent.get("minimum_delta"))
    if minimum_delta is None:
        return None, "Field 'intent.minimum_delta' must be a number >= 0.01."

    raw_guardrails = intent_data.get("guardrails", [])
    if raw_guardrails is None:
        raw_guardrails = []
    if not isinstance(raw_guardrails, list):
        return None, "Field 'guardrails' must be a list."

    guardrails = []
    seen_guardrails = set()
    for idx, entry in enumerate(raw_guardrails):
        if not isinstance(entry, dict):
            return None, f"Guardrail #{idx + 1} must be an object with metric/constraint."

        metric = _clean_metric_name(entry.get("metric"))
        if not metric:
            return None, f"Guardrail #{idx + 1} has invalid 'metric'."

        constraint = _clean_constraint(entry.get("constraint"))
        if not constraint:
            return None, (
                f"Guardrail #{idx + 1} has invalid 'constraint'. "
                "Use format like '< 1.05' or '>= 0.9'."
            )

        if metric in seen_guardrails:
            return None, f"Guardrail metric '{metric}' is duplicated."
        seen_guardrails.add(metric)
        guardrails.append({"metric": metric, "constraint": constraint})

    normalized = {
        "intent": {
            "target_metric": target_metric,
            "target_direction": target_direction,
            "minimum_delta": minimum_delta,
        },
        "guardrails": guardrails,
    }

    author = intent_data.get("author")
    if author is not None:
        if not isinstance(author, str) or not author.strip():
            return None, "Field 'author' must be a non-empty string when provided."
        normalized["author"] = author.strip()

    return normalized, None


def git_show_message(commit_hash):
    """Get the full commit message for a commit."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B", commit_hash],
        capture_output=True, text=True, cwd=_repo_root()
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")
    return result.stdout


def git_parent(commit_hash):
    """Get the parent commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", f"{commit_hash}^"],
        capture_output=True, text=True, cwd=_repo_root()
    )
    if result.returncode != 0:
        raise RuntimeError(f"Cannot get parent of {commit_hash}: {result.stderr}")
    return result.stdout.strip()


def _extract_file_at(commit_hash, repo_path):
    """Extract a file's contents at a specific commit using git show."""
    subdir = _get_subdir()
    git_path = f"{subdir}/{repo_path}"
    result = subprocess.run(
        ["git", "show", f"{commit_hash}:{git_path}"],
        capture_output=True, text=True, cwd=_repo_root()
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _setup_workdir(commit_hash):
    """Create a temp dir with the benchmark files from a specific commit.
    Uses the current bench.py and tests.py (from the verifier's version)
    but swaps in functions.py from the target commit."""
    tmpdir = tempfile.mkdtemp(prefix="autoblockchain_verify_")
    bench_dir = os.path.join(tmpdir, "benchmarks")
    os.makedirs(bench_dir)

    # Write __init__.py
    with open(os.path.join(bench_dir, "__init__.py"), "w") as f:
        f.write("")

    # Get functions.py from the target commit
    functions_src = _extract_file_at(commit_hash, "benchmarks/functions.py")
    if functions_src is None:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"Cannot extract benchmarks/functions.py at {commit_hash[:8]}")
    with open(os.path.join(bench_dir, "functions.py"), "w") as f:
        f.write(functions_src)

    # Copy current bench.py and tests.py (stable infrastructure)
    shutil.copy2(os.path.join(SCRIPT_DIR, "benchmarks", "bench.py"),
                 os.path.join(bench_dir, "bench.py"))
    shutil.copy2(os.path.join(SCRIPT_DIR, "benchmarks", "tests.py"),
                 os.path.join(bench_dir, "tests.py"))

    return tmpdir


def run_benchmarks_at(commit_hash):
    """Run benchmarks using functions.py from a specific commit. Returns metrics dict."""
    tmpdir = _setup_workdir(commit_hash)
    try:
        result = _run_python(["-m", "benchmarks.bench"], tmpdir, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Benchmarks failed at {commit_hash[:8]}: {result.stderr}")
        return json.loads(result.stdout)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_tests_at(commit_hash):
    """Run correctness tests using functions.py from a specific commit."""
    tmpdir = _setup_workdir(commit_hash)
    try:
        result = _run_python(["-m", "benchmarks.tests"], tmpdir, timeout=60)
        return result.returncode == 0, result.stdout, result.stderr
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_comparison_benchmarks(parent_hash, commit_hash):
    """Run baseline and result benchmarks in a SINGLE Python process for fair comparison.
    Uses a helper script that swaps functions.py mid-process."""
    tmpdir = tempfile.mkdtemp(prefix="autoblockchain_compare_")
    bench_dir = os.path.join(tmpdir, "benchmarks")
    os.makedirs(bench_dir)

    # Write stable infrastructure
    with open(os.path.join(bench_dir, "__init__.py"), "w") as f:
        f.write("")
    shutil.copy2(os.path.join(SCRIPT_DIR, "benchmarks", "bench.py"),
                 os.path.join(bench_dir, "bench.py"))

    # Extract both versions of functions.py
    parent_src = _extract_file_at(parent_hash, "benchmarks/functions.py")
    commit_src = _extract_file_at(commit_hash, "benchmarks/functions.py")
    if parent_src is None:
        raise RuntimeError(f"Cannot extract functions.py at {parent_hash[:8]}")
    if commit_src is None:
        raise RuntimeError(f"Cannot extract functions.py at {commit_hash[:8]}")

    parent_path = os.path.join(tmpdir, "functions_baseline.py")
    commit_path = os.path.join(tmpdir, "functions_result.py")
    with open(parent_path, "w") as f:
        f.write(parent_src)
    with open(commit_path, "w") as f:
        f.write(commit_src)

    # Keep runner inside temp workspace so sandboxed runners only need this mount.
    tmp_runner_script = os.path.join(tmpdir, "compare_runner.py")
    shutil.copy2(os.path.join(SCRIPT_DIR, "compare_runner.py"), tmp_runner_script)

    try:
        res = _run_python(
            ["compare_runner.py", "functions_baseline.py", "functions_result.py"],
            tmpdir,
            timeout=180,
        )
        if res.returncode != 0:
            raise RuntimeError(f"Comparison benchmarks failed: {res.stderr}")
        data = json.loads(res.stdout)
        return data["baseline"], data["result"]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def evaluate_constraint(constraint_str, value, baseline_value):
    """Evaluate a guardrail constraint.
    The constraint is evaluated against the ratio (value / baseline).
    e.g., '< 1.05' means the metric must not be more than 5% worse than baseline.
    """
    if not isinstance(constraint_str, str):
        return False, "Constraint must be a string"
    ratio = value / baseline_value if baseline_value != 0 else float("inf")
    # Parse constraint: "< 1.05", "> 0.8", etc.
    match = CONSTRAINT_RE.fullmatch(" ".join(constraint_str.split()))
    if not match:
        return False, f"Invalid constraint format: {constraint_str}"
    op, threshold = match.groups()
    threshold = float(threshold)
    if op == "<":
        ok = ratio < threshold
    elif op == "<=":
        ok = ratio <= threshold
    elif op == ">":
        ok = ratio > threshold
    elif op == ">=":
        ok = ratio >= threshold
    else:
        return False, f"Unknown operator: {op}"
    return ok, f"ratio={ratio:.4f} {op} {threshold} → {'PASS' if ok else 'FAIL'}"


def verify(commit_hash):
    """Run the full verification protocol on a commit. Returns verdict dict."""
    sandbox_mode = _execution_config()["mode"]
    print(f"\n{'='*60}")
    print(f"AUTOBLOCKCHAIN VERIFIER")
    print(f"{'='*60}")
    print(f"Verifying commit: {commit_hash[:12]}")
    print(f"Execution mode: {sandbox_mode}")
    if sandbox_mode == "local":
        print("Warning: local mode executes worker code on host. Use docker/custom for untrusted workers.")

    # Step 0: Parse intent from commit message
    msg = git_show_message(commit_hash)
    print(f"\nCommit message:\n{msg.strip()}\n")

    intent_data = parse_yaml_frontmatter(msg)
    if not intent_data:
        return reject(commit_hash, msg, "No intent declaration found in commit message (YAML frontmatter between --- markers)")

    intent_data, schema_error = validate_intent_schema(intent_data)
    if schema_error:
        return reject(commit_hash, msg, f"Invalid intent declaration schema: {schema_error}")

    intent = intent_data.get("intent", {})
    guardrails = intent_data.get("guardrails", [])
    target_metric = intent.get("target_metric")
    target_direction = intent.get("target_direction")
    minimum_delta = intent.get("minimum_delta")

    # Extract author from intent declaration or git commit
    author = intent_data.get("author")
    if not author:
        author_result = subprocess.run(
            ["git", "log", "-1", "--format=%an", commit_hash],
            capture_output=True, text=True, cwd=_repo_root()
        )
        author = author_result.stdout.strip() or "unknown"

    if not all([target_metric, target_direction, minimum_delta is not None]):
        return reject(commit_hash, msg, "Incomplete intent declaration: need target_metric, target_direction, minimum_delta")

    print(f"Intent: {target_direction} {target_metric} by at least {minimum_delta*100:.0f}%")
    if guardrails:
        for g in guardrails:
            print(f"  Guardrail: {g['metric']} {g['constraint']}")

    # Step 1: Get parent commit
    parent = git_parent(commit_hash)
    print(f"\nParent commit: {parent[:12]}")

    # Step 2: Run correctness tests on the new commit
    print("\n--- Running correctness tests ---")
    tests_pass, test_out, test_err = run_tests_at(commit_hash)
    if not tests_pass:
        return reject(commit_hash, msg, f"Correctness tests failed:\n{test_out}\n{test_err}",
                       intent=intent_data)

    print("Correctness tests: ALL PASSED")

    # Step 3: Run benchmarks before and after in the SAME temp dir
    # This eliminates filesystem caching differences between runs
    print("\n--- Running benchmarks (baseline then result, same environment) ---")
    baseline, result = run_comparison_benchmarks(parent, commit_hash)

    print("\nBaseline (parent):")
    for k, v in sorted(baseline.items()):
        print(f"  {k}: {v:.6f}s")

    print("\nResult (commit):")
    for k, v in sorted(result.items()):
        print(f"  {k}: {v:.6f}s")

    # Step 4: Check target
    print(f"\n--- Target Check ---")
    if target_metric not in result or target_metric not in baseline:
        return reject(commit_hash, msg, f"Target metric '{target_metric}' not found in benchmark results",
                       intent=intent_data, baseline=baseline, result=result)

    baseline_val = baseline[target_metric]
    result_val = result[target_metric]

    if baseline_val == 0:
        return reject(
            commit_hash,
            msg,
            f"Target metric '{target_metric}' has zero baseline value; cannot compute relative delta.",
            intent=intent_data,
            baseline=baseline,
            result=result,
        )

    if target_direction == "decrease":
        actual_delta = (baseline_val - result_val) / baseline_val
    elif target_direction == "increase":
        actual_delta = (result_val - baseline_val) / baseline_val
    else:
        return reject(commit_hash, msg, f"Unsupported target_direction '{target_direction}'", intent=intent_data)

    target_met = actual_delta >= minimum_delta
    print(f"  {target_metric}: {baseline_val:.6f}s → {result_val:.6f}s")
    print(f"  Actual delta: {actual_delta*100:.1f}% (required: {minimum_delta*100:.0f}%)")
    print(f"  Target: {'MET ✓' if target_met else 'NOT MET ✗'}")

    # Step 5: Check guardrails
    print(f"\n--- Guardrail Check ---")
    guardrails_ok = True
    guardrail_details = []
    for g in guardrails:
        metric = g["metric"]
        constraint = g["constraint"]
        if metric not in result or metric not in baseline:
            guardrails_ok = False
            guardrail_details.append(f"  {metric}: NOT FOUND ✗")
            continue
        ok, detail = evaluate_constraint(constraint, result[metric], baseline[metric])
        guardrail_details.append(f"  {metric}: {detail}")
        if not ok:
            guardrails_ok = False

    if not guardrails:
        print("  (none declared)")
    for d in guardrail_details:
        print(d)

    # Step 6: Anomaly detection on undeclared metrics
    print(f"\n--- Anomaly Detection (threshold: {ANOMALY_THRESHOLD*100:.0f}%) ---")
    declared_metrics = {target_metric}
    for g in guardrails:
        declared_metrics.add(g["metric"])

    anomalies = []
    for metric in result:
        if metric in declared_metrics:
            continue
        if metric not in baseline:
            continue
        b_val = baseline[metric]
        r_val = result[metric]
        if b_val == 0:
            continue
        change = (r_val - b_val) / b_val  # positive = regression, negative = improvement
        direction = "slower" if change > 0 else "faster"
        # Only flag regressions (getting slower) as anomalies, not improvements
        if change > ANOMALY_THRESHOLD:
            anomalies.append({
                "metric": metric,
                "baseline": b_val,
                "result": r_val,
                "change_pct": round(change * 100, 1),
                "direction": direction,
            })
            print(f"  ANOMALY: {metric} regressed {change*100:.1f}% ({direction}) — UNDECLARED ✗")
        else:
            print(f"  {metric}: {abs(change)*100:.1f}% ({direction}) — OK ✓")

    # Step 7: Decision
    print(f"\n{'='*60}")
    accepted = target_met and guardrails_ok and not anomalies

    # Build metric deltas
    deltas = {}
    for metric in result:
        if metric in baseline:
            b = baseline[metric]
            r = result[metric]
            deltas[metric] = {
                "baseline": b,
                "result": r,
                "change_pct": round((r - b) / b * 100, 1) if b != 0 else 0,
            }

    verdict = {
        "commit": commit_hash,
        "parent": parent,
        "author": author,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "intent": intent_data,
        "accepted": accepted,
        "target_met": target_met,
        "target_delta_pct": round(actual_delta * 100, 1),
        "guardrails_ok": guardrails_ok,
        "guardrail_details": guardrail_details,
        "anomalies": anomalies,
        "tests_passed": tests_pass,
        "baseline": baseline,
        "result": result,
        "deltas": deltas,
    }

    if not accepted:
        reasons = []
        if not target_met:
            reasons.append(f"Target not met ({actual_delta*100:.1f}% < {minimum_delta*100:.0f}%)")
        if not guardrails_ok:
            reasons.append("Guardrail breached")
        if anomalies:
            reasons.append(f"Undeclared anomalies: {', '.join(a['metric'] for a in anomalies)}")
        verdict["rejection_reasons"] = reasons
        print(f"VERDICT: REJECTED ✗")
        for r in reasons:
            print(f"  Reason: {r}")
    else:
        print(f"VERDICT: ACCEPTED ✓")
        print(f"  {target_metric} improved by {actual_delta*100:.1f}%")

    print(f"{'='*60}\n")

    # Append to chain
    append_to_chain(verdict)

    return verdict


def reject(commit_hash, msg, reason, intent=None, baseline=None, result=None):
    """Create a rejection verdict for early failures."""
    verdict = {
        "commit": commit_hash,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "intent": intent,
        "accepted": False,
        "rejection_reasons": [reason],
        "baseline": baseline,
        "result": result,
    }
    print(f"\nVERDICT: REJECTED ✗")
    print(f"  Reason: {reason}")
    print(f"{'='*60}\n")
    append_to_chain(verdict)
    return verdict


def _acquire_chain_lock(timeout_seconds=10.0, poll_interval=0.05):
    """Acquire an exclusive lock via lock-file creation."""
    deadline = time.time() + timeout_seconds
    while True:
        try:
            fd = os.open(CHAIN_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            return fd
        except FileExistsError:
            if time.time() >= deadline:
                raise RuntimeError(
                    f"Timed out acquiring chain lock: {CHAIN_LOCK_FILE}"
                )
            time.sleep(poll_interval)


def _release_chain_lock(lock_fd):
    try:
        os.close(lock_fd)
    finally:
        try:
            os.unlink(CHAIN_LOCK_FILE)
        except FileNotFoundError:
            pass


def _load_chain():
    if not os.path.exists(CHAIN_FILE):
        return []

    with open(CHAIN_FILE, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return []

    try:
        chain = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"chain.json is not valid JSON: {exc}") from exc

    if not isinstance(chain, list):
        raise RuntimeError("chain.json must contain a JSON array.")
    return chain


def _atomic_write_chain(chain):
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=".chain.", suffix=".json", dir=SCRIPT_DIR)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(chain, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CHAIN_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def append_to_chain(verdict):
    """Append a verdict to chain.json."""
    lock_fd = _acquire_chain_lock()
    try:
        chain = _load_chain()
        chain.append(verdict)
        _atomic_write_chain(chain)
    finally:
        _release_chain_lock(lock_fd)
    print(f"Result written to chain.json ({len(chain)} entries)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python verifier.py <command> [args]")
        print("Commands:")
        print("  verify <commit-hash>  — verify a commit")
        print("  status                — show chain status")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "verify":
        if len(sys.argv) < 3:
            print("Usage: python verifier.py verify <commit-hash>")
            sys.exit(1)
        commit_hash = sys.argv[2]
        # Resolve short hashes
        resolved = subprocess.run(
            ["git", "rev-parse", commit_hash],
            capture_output=True, text=True, cwd=_repo_root()
        )
        if resolved.returncode != 0:
            print(f"Error: cannot resolve commit '{commit_hash}'")
            sys.exit(1)
        full_hash = resolved.stdout.strip()
        verdict = verify(full_hash)
        sys.exit(0 if verdict["accepted"] else 1)

    elif cmd == "status":
        if not os.path.exists(CHAIN_FILE):
            print("No chain.json found. No commits verified yet.")
            sys.exit(0)
        try:
            chain = _load_chain()
        except RuntimeError as exc:
            print(f"Error reading chain.json: {exc}")
            sys.exit(1)
        accepted = sum(1 for v in chain if v.get("accepted"))
        rejected = len(chain) - accepted
        print(f"Chain: {len(chain)} proposed, {accepted} accepted, {rejected} rejected")
        for v in chain:
            status = "✓ ACCEPTED" if v.get("accepted") else "✗ REJECTED"
            commit = v.get("commit", "?")[:12]
            intent = v.get("intent", {})
            target = intent.get("intent", {}).get("target_metric", "?") if isinstance(intent, dict) else "?"
            print(f"  {commit} {status} (target: {target})")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
