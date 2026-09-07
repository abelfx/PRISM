"""
Benchmark helper for testing py-call round-trip latency and argument conversion.
"""

import time
from typing import Any, Dict, List

_call_count = 0
_latencies: List[float] = []


def ping(arg: Any) -> str:
    """Simple ping-pong test."""
    global _call_count
    _call_count += 1
    return "pong"


def echo_type_and_val(sentence: Any, goal: Any) -> str:
    """Inspect what Python receives from Janus for MeTTa atoms."""
    return f"sentence_type={type(sentence).__name__}, val={repr(sentence)} | goal_type={type(goal).__name__}, val={repr(goal)}"


def simulate_failure(sentence: Any, goal: Any) -> float:
    """Deliberately raise an exception to test error handling."""
    raise RuntimeError("Simulated internal scorer failure")


def benchmark_batch(n: int) -> Dict[str, Any]:
    """Internal Python timing benchmark for comparison."""
    start = time.perf_counter()
    for _ in range(n):
        _ = hash("sentence") ^ hash("goal")
    elapsed = time.perf_counter() - start
    return {
        "iterations": n,
        "total_time_s": elapsed,
        "avg_call_us": (elapsed / n) * 1_000_000,
    }
