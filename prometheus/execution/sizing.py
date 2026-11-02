"""Kelly sizing on a 0.01-contract grid at a bounded all-in cost; stdlib only.

For bankroll B, win probability p, cost c and unit payout, maximize
p*log(B+n*(1-c)) + (1-p)*log(B-n*c). Its continuous optimum is
B*(p-c)/(c*(1-c)); concavity leaves only its two neighbouring grid quantities,
the feasible cap and zero to compare. Existing same-outcome contracts and
their fee-inclusive cost offset terminal wealth; B includes that held cost.
Fractional Kelly scales B upstream.
"""

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext

QUANTITY_STEP = Decimal("0.01")


def kelly_order(probability, cost, bankroll, cap, held_contracts=0, held_cost=0):
    p, c, capital, cap = (Decimal(str(v)) for v in (probability, cost, bankroll, cap))
    n0, h0 = (Decimal(str(v)) for v in (held_contracts, held_cost))
    if not all(v.is_finite() for v in (p, c, capital, cap, n0, h0)):
        raise ValueError("non_finite_kelly_input")
    if n0 < 0 or h0 < 0:
        raise ValueError("negative_kelly_position")
    if not 0 < p < 1 or not 0 < c < 1 or capital <= 0 or cap < QUANTITY_STEP or p <= c:
        return None
    with localcontext() as context:
        context.prec = 40
        cap = cap.quantize(QUANTITY_STEP, rounding=ROUND_FLOOR)
        fraction = (p - c) / (1 - c)
        ideal = capital * fraction / c
        win_base, loss_base = (
            (capital + n0 - h0, capital - h0) if n0 or h0 else (capital, capital)
        )
        if loss_base <= 0:
            return None
        if n0 or h0:
            ideal = (p * (1 - c) * loss_base - (1 - p) * c * win_base) / (c * (1 - c))
        if ideal <= 0:
            return None
        candidates = {
            Decimal(0),
            min(cap, ideal.quantize(QUANTITY_STEP, rounding=ROUND_FLOOR)),
            min(cap, ideal.quantize(QUANTITY_STEP, rounding=ROUND_CEILING)),
        }
        best, growth = 0, Decimal(0)
        for count in sorted(candidates):
            loss = loss_base - count * c
            if count == 0 or loss <= 0:
                continue
            win = win_base + count * (1 - c)
            value = p * (win / win_base).ln() + (1 - p) * (loss / loss_base).ln()
            if value > growth:
                best, growth = count, value
        if not best:
            return None
        return {
            "count": f"{best:.2f}",
            "quantity_step": str(QUANTITY_STEP),
            "full_kelly_fraction": str(fraction),
            "continuous_contracts": str(ideal),
            "expected_log_growth": str(growth),
        }
