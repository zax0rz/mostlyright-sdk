"""Shared timing + status-code + body-size helpers for source_limits spikes.

Not a test module. Not under tradewinds.* namespace. Runs as stand-alone CLI.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field


@dataclass
class RequestResult:
    url: str
    status_code: int
    elapsed_s: float
    body_size_bytes: int
    error: str | None = None


@dataclass
class SpikeResult:
    n: int
    repeats: int
    per_request: list[RequestResult] = field(default_factory=list)

    @property
    def status_distribution(self) -> dict[int, int]:
        return dict(Counter(r.status_code for r in self.per_request if r.error is None))

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.per_request if r.error is not None)

    @property
    def elapsed_p50(self) -> float:
        elapsed = [r.elapsed_s for r in self.per_request if r.error is None]
        return statistics.median(elapsed) if elapsed else float("nan")

    @property
    def elapsed_p95(self) -> float:
        return percentile([r.elapsed_s for r in self.per_request if r.error is None], 95)

    @property
    def elapsed_p99(self) -> float:
        return percentile([r.elapsed_s for r in self.per_request if r.error is None], 99)

    @property
    def mean_body_size(self) -> float:
        sizes = [r.body_size_bytes for r in self.per_request if r.error is None]
        return statistics.mean(sizes) if sizes else float("nan")

    @property
    def max_body_size(self) -> int:
        sizes = [r.body_size_bytes for r in self.per_request if r.error is None]
        return max(sizes) if sizes else 0


def percentile(values: list[float], p: int) -> float:
    """Linear-interpolated percentile. Returns NaN on empty input."""
    if not values:
        return float("nan")
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (p / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def fan_out(
    urls: list[str],
    max_workers: int,
    fetch: Callable[[str], RequestResult],
) -> list[RequestResult]:
    """Run ``fetch(url)`` for each URL with ThreadPoolExecutor(max_workers).

    Exceptions inside ``fetch`` are caught and recorded as ``RequestResult.error``
    so the per-thread error path is observable in the spike output.
    """
    results: list[RequestResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch, u): u for u in urls}
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as exc:
                results.append(
                    RequestResult(
                        url=futures[f],
                        status_code=0,
                        elapsed_s=0.0,
                        body_size_bytes=0,
                        error=str(exc),
                    )
                )
    return results


def render_markdown_row(label: str, result: SpikeResult) -> str:
    """One markdown table row pasteable into SOURCE-LIMITS.md."""
    return (
        f"| {label} | {result.n} | {result.elapsed_p50:.2f} | {result.elapsed_p95:.2f} "
        f"| {result.elapsed_p99:.2f} | {result.status_distribution} "
        f"| {result.mean_body_size:.0f} | {result.max_body_size} | {result.error_count} |"
    )
