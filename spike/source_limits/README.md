# spike/source_limits

One-shot empirical characterization of AWC, GHCNh, IEM concurrent-request
behavior. Output: [`.planning/research/SOURCE-LIMITS.md`](../../.planning/research/SOURCE-LIMITS.md).

## Why these are spikes, not tests

These scripts hit real public APIs and intentionally fire up to N=16 concurrent
requests. Tradewinds policy (CLAUDE.md):

- Tests under `tests/` use recorded fixtures via pytest-recording.
- Live tests are tagged `@pytest.mark.live` and excluded from CI.

These scripts are neither — they characterize endpoint behavior empirically and
persist their output as a planning artifact. They are kept in version control so
re-validation in v0.2 is one command.

## How to run

```bash
# Full sweep (~5-10 min total at the default --repeats; ~1 min for the quick smoke below)
uv run python -m spike.source_limits.awc_concurrent --n-levels 1,2,4,8,16 --repeats 5
uv run python -m spike.source_limits.ghcnh_concurrent --n-levels 1,2,4,8,16 --repeats 5
uv run python -m spike.source_limits.iem_shared_ip_spike --repeats 10

# Quick smoke run (~30s; what the Phase 1.5 PERF-05 deliverable used)
uv run python -m spike.source_limits.awc_concurrent --n-levels 1,2,4 --repeats 2
uv run python -m spike.source_limits.ghcnh_concurrent --n-levels 1,2,4 --repeats 2
uv run python -m spike.source_limits.iem_shared_ip_spike --repeats 4
```

Each script prints a markdown table to stdout that you paste into the
corresponding section of `.planning/research/SOURCE-LIMITS.md`.

## Internal unit tests

`spike/source_limits/test_common.py` covers the percentile / aggregation /
markdown-render helpers in `_common.py`. Run::

    uv run pytest spike/source_limits/test_common.py -v

## When to re-run

- v0.2 milestone — confirm rate limits haven't tightened.
- After any IEM / AWC / NCEI published policy change.
- When PERF-04 wall-time regresses unexpectedly in CI or in production.

## Operating principles

- **N=16 is the upper bound** these scripts probe. Higher than that probably
  violates upstream ToS norms for an SDK; if tradewinds ever needs more
  concurrency, the conversation belongs in v0.2 (a hosted backend with a real
  rate-limiter, not a local SDK).
- **The recommendation logic in `iem_shared_ip_spike.recommend_option` is
  deterministic.** It maps 503/error counts to Option A/B/C with no narrative
  override. If you want to second-guess it, change the threshold there, not by
  hand-editing the SOURCE-LIMITS.md output.
