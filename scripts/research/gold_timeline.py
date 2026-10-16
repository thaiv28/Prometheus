"""Read cached full-minute gold graphs; no JavaScript execution or guessing."""

import math
import re
from collections import Counter


def parse_gold(html):
    match = re.search(r"var\s+golddatas\s*=\s*\{(.*?)\n\s*\};", html, re.S)
    if not match:
        raise ValueError("missing_gold_graph")
    block = match.group(1)
    labels = re.search(r"labels:\s*\[([^]]*)\]", block)
    series = re.findall(
        r"label:\s*['\"]([^'\"]+)['\"].*?data:\s*\[([^]]*)\].*?borderColor:\s*['\"]rgba\(([^)]*)\)",
        block,
        re.S,
    )
    if labels is None or len(series) != 10:
        raise ValueError("unsupported_gold_graph")
    clocks = [int(v) for v in re.findall(r"['\"](\d+)['\"]", labels.group(1))]
    if not clocks or clocks != sorted(clocks):
        raise ValueError("unordered_clock")
    arrays = []
    for i, (role, numbers, color) in enumerate(series):
        if role != ("TOP", "JGL", "MID", "BOT", "SPT")[i % 5]:
            raise ValueError("unexpected_role_order")
        rgb = [int(v) for v in color.split(",")[:3]]
        if (i < 5 and rgb[2] <= rgb[0]) or (i >= 5 and rgb[0] <= rgb[2]):
            raise ValueError("unexpected_side_colors")
        if not re.fullmatch(r"[\s\d.,]+", numbers):
            raise ValueError("nonnumeric_gold_graph")
        values = [float(v) for v in numbers.split(",") if v.strip()]
        if len(values) != len(clocks) or not all(
            math.isfinite(v) and v >= 0 for v in values
        ):
            raise ValueError("invalid_gold_arrays")
        arrays.append(values)
    counts = Counter(clocks)
    # Last partial-minute and full-minute entries can share a label. Drop both.
    return {
        minute: (sum(a[i] for a in arrays[:5]), sum(a[i] for a in arrays[5:]))
        for i, minute in enumerate(clocks)
        if counts[minute] == 1
    }
