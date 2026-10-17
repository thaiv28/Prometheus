"""Whole-contract Kelly sizing at a bounded all-in cost; standard library only.

For bankroll B, win probability p, cost c and unit payout, maximize
p*log(B+n*(1-c)) + (1-p)*log(B-n*c). Its continuous optimum is
B*(p-c)/(c*(1-c)); concavity leaves only its two neighbouring integers,
the feasible cap and zero to compare. Fractional Kelly scales B upstream.
"""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext


def kelly_order(probability, cost, bankroll, cap):
    p, c, capital = (Decimal(str(v)) for v in (probability, cost, bankroll))
    if not all(v.is_finite() for v in (p, c, capital)):
        raise ValueError("non_finite_kelly_input")
    if not 0 < p < 1 or not 0 < c < 1 or capital <= 0 or cap < 1 or p <= c:
        return None
    with localcontext() as context:
        context.prec = 40
        fraction = (p - c) / (1 - c)
        ideal = capital * fraction / c
        candidates = {
            0,
            min(cap, int(ideal.to_integral_value(rounding=ROUND_FLOOR))),
            min(cap, int(ideal.to_integral_value(rounding=ROUND_CEILING))),
        }
        best, growth = 0, Decimal(0)
        for count in sorted(candidates):
            loss = capital - count * c
            if count == 0 or loss <= 0:
                continue
            win = capital + count * (1 - c)
            value = p * (win / capital).ln() + (1 - p) * (loss / capital).ln()
            if value > growth:
                best, growth = count, value
        if not best:
            return None
        return {
            "count": best,
            "full_kelly_fraction": str(fraction),
            "continuous_contracts": str(ideal),
            "expected_log_growth": str(growth),
        }
