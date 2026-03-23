"""
Comparison benchmark runner — used by the verifier.
Loads two versions of functions.py and benchmarks both using interleaved runs
for fair comparison. Each function is timed baseline→result→baseline→result→...
and the median is taken, eliminating ordering bias from memory/cache effects.

Usage: python compare_runner.py <baseline_functions.py> <result_functions.py>
Outputs: JSON with {"baseline": {...}, "result": {...}}
"""

import gc
import importlib.util
import json
import random
import statistics
import sys
import time


def load_functions(path):
    """Load a functions.py file as a standalone module."""
    spec = importlib.util.spec_from_file_location("funcs_" + path.replace("/", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_json_blob(rng, depth=5):
    """Generate a deterministic nested JSON string."""
    def gen(d):
        if d <= 0:
            choice = rng.randint(0, 3)
            if choice == 0:
                return str(rng.randint(-1000, 1000))
            if choice == 1:
                word = rng.choice(["alpha", "beta", "gamma", "delta", "epsilon"])
                return '"' + word + '"'
            if choice == 2:
                return rng.choice(["true", "false"])
            return "null"
        if rng.random() < 0.5:
            n = rng.randint(2, 5)
            pairs = []
            for _ in range(n):
                k = '"key_' + str(rng.randint(0, 999)) + '"'
                pairs.append(k + ": " + gen(d - 1))
            return "{" + ", ".join(pairs) + "}"
        else:
            n = rng.randint(2, 6)
            items = [gen(d - 1) for _ in range(n)]
            return "[" + ", ".join(items) + "]"
    return gen(depth)


def time_function(fn, rounds=5):
    """Time a function over multiple rounds, return median."""
    times = []
    for _ in range(rounds):
        gc.collect()
        gc.disable()
        start = time.perf_counter()
        fn()
        elapsed = time.perf_counter() - start
        gc.enable()
        times.append(elapsed)
    return statistics.median(times)


def generate_inputs():
    """Generate all benchmark inputs deterministically."""
    SEED = 42
    rng = random.Random(SEED)

    mat_size = 150
    mat_a = [[rng.randint(-100, 100) for _ in range(mat_size)] for _ in range(mat_size)]
    mat_b = [[rng.randint(-100, 100) for _ in range(mat_size)] for _ in range(mat_size)]

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    lcs_s1 = "".join(rng.choice(alphabet) for _ in range(800))
    lcs_s2 = "".join(rng.choice(alphabet) for _ in range(800))

    sieve_n = 500_000

    json_blobs = [make_json_blob(rng, depth=5) for _ in range(100)]

    knapsack_items = [(rng.randint(1, 50), rng.randint(1, 100)) for _ in range(500)]
    knapsack_cap = 2000

    return {
        "mat_a": mat_a, "mat_b": mat_b,
        "lcs_s1": lcs_s1, "lcs_s2": lcs_s2,
        "sieve_n": sieve_n,
        "json_blobs": json_blobs,
        "knapsack_items": knapsack_items, "knapsack_cap": knapsack_cap,
    }


def bench_one_function(name, baseline_fn, result_fn, rounds=5):
    """Benchmark a single function from both modules using interleaved runs.
    Returns (baseline_time, result_time)."""
    baseline_times = []
    result_times = []

    for _ in range(rounds):
        # Alternate: baseline first, then result
        gc.collect()
        gc.disable()
        start = time.perf_counter()
        baseline_fn()
        b_time = time.perf_counter() - start
        gc.enable()

        gc.collect()
        gc.disable()
        start = time.perf_counter()
        result_fn()
        r_time = time.perf_counter() - start
        gc.enable()

        baseline_times.append(b_time)
        result_times.append(r_time)

    return statistics.median(baseline_times), statistics.median(result_times)


if __name__ == "__main__":
    baseline_path = sys.argv[1]
    result_path = sys.argv[2]

    baseline_funcs = load_functions(baseline_path)
    result_funcs = load_functions(result_path)
    inputs = generate_inputs()

    # Warmup both modules
    small_mat = [[1, 2], [3, 4]]
    for funcs in [baseline_funcs, result_funcs]:
        funcs.matrix_multiply(small_mat, small_mat)
        funcs.longest_common_subsequence("AB", "BA")
        funcs.prime_sieve(100)
        funcs.json_parse('{"a": 1}')
        funcs.knapsack([(1, 2)], 3)

    baseline = {}
    result = {}

    # Interleaved benchmarks for each function
    benchmarks = [
        ("bench_matrix_multiply",
         lambda f: f.matrix_multiply(inputs["mat_a"], inputs["mat_b"])),
        ("bench_lcs",
         lambda f: f.longest_common_subsequence(inputs["lcs_s1"], inputs["lcs_s2"])),
        ("bench_prime_sieve",
         lambda f: f.prime_sieve(inputs["sieve_n"])),
        ("bench_json_parse",
         lambda f: [f.json_parse(b) for b in inputs["json_blobs"]]),
        ("bench_knapsack",
         lambda f: f.knapsack(inputs["knapsack_items"], inputs["knapsack_cap"])),
    ]

    for name, make_fn in benchmarks:
        b_time, r_time = bench_one_function(
            name,
            lambda _mf=make_fn, _bf=baseline_funcs: _mf(_bf),
            lambda _mf=make_fn, _rf=result_funcs: _mf(_rf),
            rounds=5,
        )
        baseline[name] = round(b_time, 6)
        result[name] = round(r_time, 6)

    print(json.dumps({"baseline": baseline, "result": result}))
