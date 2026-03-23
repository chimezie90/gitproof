"""
Five pure Python benchmark functions with naive implementations.
These are the optimization targets for Autoblockchain workers.
"""


def matrix_multiply(a, b):
    """Optimized matrix multiplication — pushes inner loop to C via map+operator.mul."""
    from operator import mul
    bt = list(zip(*b))
    return [[sum(map(mul, row, col)) for col in bt] for row in a]


def longest_common_subsequence(s1, s2):
    """Standard DP longest common subsequence. Returns the LCS string."""
    n, m = len(s1), len(s2)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    # Backtrack to find the actual subsequence
    lcs = []
    i, j = n, m
    while i > 0 and j > 0:
        if s1[i - 1] == s2[j - 1]:
            lcs.append(s1[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return "".join(reversed(lcs))


def prime_sieve(n):
    """Basic Sieve of Eratosthenes. Returns list of primes up to n."""
    if n < 2:
        return []
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n ** 0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, n + 1, i):
                is_prime[j] = False
    return [i for i, v in enumerate(is_prime) if v]


def json_parse(text):
    """Recursive descent parser for a subset of JSON (strings, numbers, bools, null, arrays, objects)."""
    pos = [0]  # mutable index

    def skip_ws():
        while pos[0] < len(text) and text[pos[0]] in " \t\n\r":
            pos[0] += 1

    def parse_value():
        skip_ws()
        if pos[0] >= len(text):
            raise ValueError("Unexpected end of input")
        c = text[pos[0]]
        if c == '"':
            return parse_string()
        if c == '{':
            return parse_object()
        if c == '[':
            return parse_array()
        if c == 't':
            return parse_literal("true", True)
        if c == 'f':
            return parse_literal("false", False)
        if c == 'n':
            return parse_literal("null", None)
        if c == '-' or c.isdigit():
            return parse_number()
        raise ValueError(f"Unexpected character: {c}")

    def parse_string():
        pos[0] += 1  # skip opening quote
        chars = []
        while pos[0] < len(text):
            c = text[pos[0]]
            if c == '\\':
                pos[0] += 1
                esc = text[pos[0]]
                if esc == '"':
                    chars.append('"')
                elif esc == '\\':
                    chars.append('\\')
                elif esc == '/':
                    chars.append('/')
                elif esc == 'n':
                    chars.append('\n')
                elif esc == 't':
                    chars.append('\t')
                elif esc == 'r':
                    chars.append('\r')
                elif esc == 'b':
                    chars.append('\b')
                elif esc == 'f':
                    chars.append('\f')
                else:
                    chars.append(esc)
                pos[0] += 1
            elif c == '"':
                pos[0] += 1
                return "".join(chars)
            else:
                chars.append(c)
                pos[0] += 1
        raise ValueError("Unterminated string")

    def parse_number():
        start = pos[0]
        if text[pos[0]] == '-':
            pos[0] += 1
        while pos[0] < len(text) and text[pos[0]].isdigit():
            pos[0] += 1
        if pos[0] < len(text) and text[pos[0]] == '.':
            pos[0] += 1
            while pos[0] < len(text) and text[pos[0]].isdigit():
                pos[0] += 1
        if pos[0] < len(text) and text[pos[0]] in 'eE':
            pos[0] += 1
            if pos[0] < len(text) and text[pos[0]] in '+-':
                pos[0] += 1
            while pos[0] < len(text) and text[pos[0]].isdigit():
                pos[0] += 1
        num_str = text[start:pos[0]]
        if '.' in num_str or 'e' in num_str or 'E' in num_str:
            return float(num_str)
        return int(num_str)

    def parse_array():
        pos[0] += 1  # skip [
        result = []
        skip_ws()
        if pos[0] < len(text) and text[pos[0]] == ']':
            pos[0] += 1
            return result
        while True:
            result.append(parse_value())
            skip_ws()
            if pos[0] < len(text) and text[pos[0]] == ',':
                pos[0] += 1
            else:
                break
        skip_ws()
        if pos[0] < len(text) and text[pos[0]] == ']':
            pos[0] += 1
        else:
            raise ValueError("Expected ']'")
        return result

    def parse_object():
        pos[0] += 1  # skip {
        result = {}
        skip_ws()
        if pos[0] < len(text) and text[pos[0]] == '}':
            pos[0] += 1
            return result
        while True:
            skip_ws()
            key = parse_string()
            skip_ws()
            if pos[0] < len(text) and text[pos[0]] == ':':
                pos[0] += 1
            else:
                raise ValueError("Expected ':'")
            value = parse_value()
            result[key] = value
            skip_ws()
            if pos[0] < len(text) and text[pos[0]] == ',':
                pos[0] += 1
            else:
                break
        skip_ws()
        if pos[0] < len(text) and text[pos[0]] == '}':
            pos[0] += 1
        else:
            raise ValueError("Expected '}'")
        return result

    def parse_literal(expected, value):
        end = pos[0] + len(expected)
        if text[pos[0]:end] == expected:
            pos[0] = end
            return value
        raise ValueError(f"Expected {expected}")

    result = parse_value()
    skip_ws()
    return result


def knapsack(items, capacity):
    """
    0/1 knapsack via DP.
    items: list of (weight, value) tuples
    capacity: integer max weight
    Returns (max_value, selected_indices)
    """
    n = len(items)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        w, v = items[i - 1]
        for c in range(capacity + 1):
            if w <= c:
                dp[i][c] = max(dp[i - 1][c], dp[i - 1][c - w] + v)
            else:
                dp[i][c] = dp[i - 1][c]
    # Backtrack to find selected items
    selected = []
    c = capacity
    for i in range(n, 0, -1):
        if dp[i][c] != dp[i - 1][c]:
            selected.append(i - 1)
            c -= items[i - 1][0]
    selected.reverse()
    return dp[n][capacity], selected
