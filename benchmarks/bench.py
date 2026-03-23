"""
Benchmark runner with deterministic inputs and fixed iteration counts.
Outputs JSON with metric names like bench_matrix_multiply, bench_prime_sieve, etc.
"""

import json
import random
import sys
import os
import timeit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.functions import (
    matrix_multiply,
    longest_common_subsequence,
    prime_sieve,
    json_parse,
    knapsack,
)

# Fixed seed for deterministic inputs
SEED = 42
ITERATIONS = 3  # timeit repeats — inputs are large enough to dominate noise


def make_matrix(rows, cols, rng):
    return [[rng.randint(-100, 100) for _ in range(cols)] for _ in range(rows)]


def make_json_blob(rng, depth=3):
    """Generate a deterministic nested JSON string."""
    def gen(d):
        if d <= 0:
            choice = rng.randint(0, 3)
            if choice == 0:
                return str(rng.randint(-1000, 1000))
            if choice == 1:
                return f'"{rng.choice(["alpha", "beta", "gamma", "delta", "epsilon"])}"'
            if choice == 2:
                return rng.choice(["true", "false"])
            return "null"
        if rng.random() < 0.5:
            # object
            n = rng.randint(2, 5)
            keys = [f'"key_{rng.randint(0, 999)}"' for _ in range(n)]
            pairs = [f'{k}: {gen(d - 1)}' for k in keys]
            return "{" + ", ".join(pairs) + "}"
        else:
            # array
            n = rng.randint(2, 6)
            items = [gen(d - 1) for _ in range(n)]
            return "[" + ", ".join(items) + "]"
    return gen(depth)


def make_lcs_strings(rng, length=300):
    """Generate two strings with ~30% overlap for LCS benchmark."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    s1 = "".join(rng.choice(alphabet) for _ in range(length))
    s2 = "".join(rng.choice(alphabet) for _ in range(length))
    return s1, s2


def make_knapsack_items(rng, n=200):
    """Generate n items with random weights and values."""
    return [(rng.randint(1, 50), rng.randint(1, 100)) for _ in range(n)]


def run_benchmarks():
    """Run all benchmarks and return results dict."""
    rng = random.Random(SEED)

    # Prepare deterministic inputs — large enough that each benchmark takes ~0.5-2s
    mat_size = 150
    mat_a = make_matrix(mat_size, mat_size, rng)
    mat_b = make_matrix(mat_size, mat_size, rng)

    lcs_s1, lcs_s2 = make_lcs_strings(rng, 800)

    sieve_n = 500_000

    json_blobs = [make_json_blob(rng, depth=5) for _ in range(100)]

    knapsack_items = make_knapsack_items(rng, 500)
    knapsack_cap = 2000

    results = {}

    # Benchmark each function
    t = timeit.timeit(lambda: matrix_multiply(mat_a, mat_b), number=ITERATIONS)
    results["bench_matrix_multiply"] = round(t / ITERATIONS, 6)

    t = timeit.timeit(lambda: longest_common_subsequence(lcs_s1, lcs_s2), number=ITERATIONS)
    results["bench_lcs"] = round(t / ITERATIONS, 6)

    t = timeit.timeit(lambda: prime_sieve(sieve_n), number=ITERATIONS)
    results["bench_prime_sieve"] = round(t / ITERATIONS, 6)

    def parse_all():
        for blob in json_blobs:
            json_parse(blob)

    t = timeit.timeit(parse_all, number=ITERATIONS)
    results["bench_json_parse"] = round(t / ITERATIONS, 6)

    t = timeit.timeit(lambda: knapsack(knapsack_items, knapsack_cap), number=ITERATIONS)
    results["bench_knapsack"] = round(t / ITERATIONS, 6)

    return results


if __name__ == "__main__":
    results = run_benchmarks()
    print(json.dumps(results, indent=2))
