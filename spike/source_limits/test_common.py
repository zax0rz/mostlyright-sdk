"""Tests for spike/source_limits/_common.py percentile + helpers.

Self-contained -- no network, no tradewinds imports. Lives in spike/ so the
fast suite picks it up without spike/ needing to be a package proper.
"""

from __future__ import annotations

import math

from spike.source_limits._common import (
    RequestResult,
    SpikeResult,
    percentile,
    render_markdown_row,
)


def test_percentile_p50_is_median() -> None:
    assert percentile([1, 2, 3, 4, 5], 50) == 3.0


def test_percentile_p99_includes_tail_sample() -> None:
    # 99 ones and one 100: with linear interpolation between k=98 (value 1.0) and
    # k=99 (value 100.0), p99 = 1.0 + (100.0 - 1.0) * 0.01 ~= 1.99. The point is
    # that p99 differs from p50 in the presence of an upper-tail outlier.
    p50 = percentile([1.0] * 99 + [100.0], 50)
    p99 = percentile([1.0] * 99 + [100.0], 99)
    assert p99 > p50
    # p100 should equal the max.
    assert percentile([1.0] * 99 + [100.0], 100) == 100.0


def test_percentile_empty_returns_nan() -> None:
    assert math.isnan(percentile([], 95))


def test_spike_result_aggregations() -> None:
    r = SpikeResult(n=4, repeats=2)
    r.per_request = [
        RequestResult(url="u", status_code=200, elapsed_s=0.1, body_size_bytes=100),
        RequestResult(url="u", status_code=200, elapsed_s=0.2, body_size_bytes=200),
        RequestResult(url="u", status_code=200, elapsed_s=0.3, body_size_bytes=300),
        RequestResult(url="u", status_code=429, elapsed_s=0.4, body_size_bytes=400),
        RequestResult(url="u", status_code=0, elapsed_s=0.0, body_size_bytes=0, error="boom"),
    ]
    assert r.error_count == 1
    assert r.status_distribution == {200: 3, 429: 1}
    assert r.elapsed_p50 == 0.25  # median of [0.1, 0.2, 0.3, 0.4]
    assert r.mean_body_size == 250.0
    assert r.max_body_size == 400


def test_render_markdown_row_format() -> None:
    r = SpikeResult(n=2, repeats=1)
    r.per_request = [
        RequestResult(url="u", status_code=200, elapsed_s=0.1, body_size_bytes=100),
        RequestResult(url="u", status_code=200, elapsed_s=0.2, body_size_bytes=200),
    ]
    row = render_markdown_row("baseline", r)
    assert row.startswith("| baseline | 2 |")
    assert "{200: 2}" in row
    # Body size mean = 150, max = 200
    assert "150" in row
    assert "200" in row
