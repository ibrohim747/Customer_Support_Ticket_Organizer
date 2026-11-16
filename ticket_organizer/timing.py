"""Measure how long each step takes and print it in a readable form."""
from contextlib import contextmanager
from time import perf_counter


@contextmanager
def timed(timings, step):
    """`with timed(timings, "categorize"): ...` -> timings["categorize"] = seconds.

    perf_counter is a clock made for measuring durations (not affected by changing the system time).
    `timings` may be None: then nothing is recorded (callers that do not need times).
    """
    start = perf_counter()
    try:
        yield
    finally:
        if timings is not None:
            timings[step] = perf_counter() - start


def format_duration(seconds):
    if seconds < 0.01:
        return f"{seconds * 1000:.1f} ms"  # 0.4 ms instead of a confusing "0 ms"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)} min {rest:.0f} s"


def format_timings(timings, total=True):
    """Time block for the bottom of a step's output; with several steps also a total line."""
    show_total = total and len(timings) > 1
    labels = list(timings) + (["total"] if show_total else [])
    width = max(len(label) for label in labels) + 1  # +1 for the ":" -> all numbers in one column
    lines = ["Time:"]
    lines += [f"  {step + ':':<{width}} {format_duration(t)}" for step, t in timings.items()]
    if show_total:
        lines.append(f"  {'total:':<{width}} {format_duration(sum(timings.values()))}")
    return "\n".join(lines)
