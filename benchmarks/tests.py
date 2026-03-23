"""
Correctness tests with golden inputs/outputs for each benchmark function.
Used by the verifier as the non-negotiable global health check (100% pass rate required).
"""

import sys
import os

# Ensure the repo root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmarks.functions import (
    matrix_multiply,
    longest_common_subsequence,
    prime_sieve,
    json_parse,
    knapsack,
)

TESTS = []


def test(name):
    def decorator(fn):
        TESTS.append((name, fn))
        return fn
    return decorator


# --- matrix_multiply ---

@test("matrix_multiply: identity")
def _():
    a = [[1, 0], [0, 1]]
    b = [[5, 3], [2, 7]]
    assert matrix_multiply(a, b) == [[5, 3], [2, 7]]

@test("matrix_multiply: 3x3")
def _():
    a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    b = [[9, 8, 7], [6, 5, 4], [3, 2, 1]]
    expected = [[30, 24, 18], [84, 69, 54], [138, 114, 90]]
    assert matrix_multiply(a, b) == expected

@test("matrix_multiply: non-square")
def _():
    a = [[1, 2], [3, 4], [5, 6]]  # 3x2
    b = [[7, 8, 9], [10, 11, 12]]  # 2x3
    expected = [[27, 30, 33], [61, 68, 75], [95, 106, 117]]
    assert matrix_multiply(a, b) == expected

@test("matrix_multiply: 1x1")
def _():
    assert matrix_multiply([[3]], [[7]]) == [[21]]


# --- longest_common_subsequence ---

@test("lcs: classic example")
def _():
    result = longest_common_subsequence("ABCBDAB", "BDCAB")
    assert len(result) == 4  # BCAB or BDAB — both valid LCS of length 4

@test("lcs: identical strings")
def _():
    assert longest_common_subsequence("HELLO", "HELLO") == "HELLO"

@test("lcs: no common")
def _():
    assert longest_common_subsequence("ABC", "XYZ") == ""

@test("lcs: one empty")
def _():
    assert longest_common_subsequence("", "ABC") == ""

@test("lcs: single char match")
def _():
    assert longest_common_subsequence("A", "A") == "A"


# --- prime_sieve ---

@test("prime_sieve: up to 30")
def _():
    assert prime_sieve(30) == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

@test("prime_sieve: up to 1")
def _():
    assert prime_sieve(1) == []

@test("prime_sieve: up to 2")
def _():
    assert prime_sieve(2) == [2]

@test("prime_sieve: up to 100 count")
def _():
    assert len(prime_sieve(100)) == 25

@test("prime_sieve: up to 10000 count")
def _():
    assert len(prime_sieve(10000)) == 1229


# --- json_parse ---

@test("json_parse: simple object")
def _():
    assert json_parse('{"a": 1, "b": "hello"}') == {"a": 1, "b": "hello"}

@test("json_parse: nested")
def _():
    s = '{"x": [1, 2, {"y": true}], "z": null}'
    assert json_parse(s) == {"x": [1, 2, {"y": True}], "z": None}

@test("json_parse: array of arrays")
def _():
    assert json_parse("[[1,2],[3,4]]") == [[1, 2], [3, 4]]

@test("json_parse: string escapes")
def _():
    assert json_parse(r'"hello\nworld"') == "hello\nworld"

@test("json_parse: number formats")
def _():
    assert json_parse("42") == 42
    assert json_parse("-3.14") == -3.14
    assert json_parse("1e10") == 1e10

@test("json_parse: booleans and null")
def _():
    assert json_parse("[true, false, null]") == [True, False, None]


# --- knapsack ---

@test("knapsack: classic")
def _():
    items = [(2, 3), (3, 4), (4, 5), (5, 6)]
    max_val, selected = knapsack(items, 8)
    assert max_val == 10
    # Verify selected items respect capacity
    total_weight = sum(items[i][0] for i in selected)
    total_value = sum(items[i][1] for i in selected)
    assert total_weight <= 8
    assert total_value == max_val

@test("knapsack: zero capacity")
def _():
    items = [(1, 10), (2, 20)]
    max_val, selected = knapsack(items, 0)
    assert max_val == 0
    assert selected == []

@test("knapsack: all fit")
def _():
    items = [(1, 5), (2, 10), (3, 15)]
    max_val, selected = knapsack(items, 10)
    assert max_val == 30
    assert sorted(selected) == [0, 1, 2]

@test("knapsack: single item fits")
def _():
    items = [(10, 100)]
    max_val, selected = knapsack(items, 10)
    assert max_val == 100
    assert selected == [0]

@test("knapsack: single item too heavy")
def _():
    items = [(10, 100)]
    max_val, selected = knapsack(items, 5)
    assert max_val == 0
    assert selected == []


def run_all():
    """Run all tests. Returns (passed, failed, errors) counts."""
    passed = 0
    failed = 0
    errors = []
    for name, fn in TESTS:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            failed += 1
            errors.append((name, f"FAIL: {e}"))
        except Exception as e:
            failed += 1
            errors.append((name, f"ERROR: {e}"))
    return passed, failed, errors


if __name__ == "__main__":
    passed, failed, errors = run_all()
    total = passed + failed
    for name, msg in errors:
        print(f"  FAIL  {name}: {msg}")
    print(f"\n{passed}/{total} tests passed")
    if failed:
        sys.exit(1)
    print("All tests passed!")
