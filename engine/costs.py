"""What Claude costs per episode (from ep.usage) plus a measured flat rate for Gemini art/voice. `pipeline.py cost`; metrics.py reads it."""
from common import load_episodes


# $ per million tokens (input, output); cache writes bill 1.25x input, cache reads 0.1x. Thinking is in "out".
PRICES = {"sonnet": (2.00, 10.00), "haiku": (0.10, 0.50), "opus": (4.00, 20.00)}


GEMINI_PER_EPISODE = 0.22  # art + narration, from Google Cloud billing (Oct 29-31 2026, one episode a day, after savings)


def call_cost(row):
    p_in, p_out = next((v for k, v in PRICES.items() if k in row.get("model", "")), PRICES["sonnet"])
    return (row.get("in", 0) * p_in + row.get("cache_write", 0) * p_in * 1.25
            + row.get("cache_read", 0) * p_in * 0.1 + row.get("out", 0) * p_out) / 1e6


def cmd_cost(a):
    """Claude cost per episode from ep.usage, plus Gemini art/voice (a measured flat rate), and what a month costs."""
    eps = sorted((e for e in load_episodes().values() if e.get("usage")), key=lambda e: e["id"])
    steps, totals = {}, []
    for ep in eps:
        total = sum(call_cost(r) for r in ep["usage"])
        totals.append(total)
        for r in ep["usage"]:
            steps.setdefault(r["step"], []).append(call_cost(r))
        print(f"{ep['id']}  ${total:.3f}  {ep['saint']['name']}  ({len(ep['usage'])} calls)")
    if not totals:
        return print("No episodes with usage yet")
    avg = sum(totals) / len(totals)
    print(f"\nAverage ${avg:.3f}/episode -> ${avg * 30:.2f} per 30 days of Claude")
    both = avg + GEMINI_PER_EPISODE
    print(f"With Gemini (~${GEMINI_PER_EPISODE:.2f}/episode): ${both:.2f}/episode -> ${both * 30:.2f} per 30 days")
    print("By step (average per call): " + ", ".join(f"{k} ${sum(v) / len(v):.3f}" for k, v in steps.items()))
