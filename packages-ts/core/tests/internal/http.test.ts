import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MockInstance } from "vitest";

import {
  AuthenticationError,
  ForbiddenError,
  NotFoundError,
  RateLimitError,
  ServerError,
  TherminalError,
  ValidationError,
} from "../../src/exceptions/index.js";
import { fetchWithRetry } from "../../src/internal/http.js";

type FetchFn = typeof globalThis.fetch;
// Use the broadest MockInstance shape; we don't rely on parameter contravariance.
// `vi.spyOn(globalThis, "fetch")` returns the precise instance; we widen via
// `unknown` to keep the test file type-stable across vitest type updates.
let fetchSpy: MockInstance<FetchFn>;

beforeEach(() => {
  fetchSpy = vi.spyOn(globalThis, "fetch") as unknown as MockInstance<FetchFn>;
});

afterEach(() => {
  fetchSpy.mockRestore();
  vi.restoreAllMocks();
});

function makeResponse(status: number, body = ""): Response {
  return new Response(body, {
    status,
    headers: { "content-type": "text/plain" },
  });
}

describe("fetchWithRetry — success path", () => {
  it("returns the Response on 200", async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(200, "ok"));
    const res = await fetchWithRetry("https://example.test/ok");
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("ok");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("forwards method + headers", async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(200, "ok"));
    await fetchWithRetry("https://example.test/ok", {
      method: "POST",
      headers: { "X-Trace": "abc" },
      userAgent: "tradewinds-test/1.0",
    });
    const init = fetchSpy.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["X-Trace"]).toBe("abc");
    expect(headers["User-Agent"]).toBe("tradewinds-test/1.0");
  });
});

describe("fetchWithRetry — retry path", () => {
  it("retries on 503 and returns 200 on second attempt", async () => {
    fetchSpy
      .mockResolvedValueOnce(makeResponse(503))
      .mockResolvedValueOnce(makeResponse(200, "ok"));
    const res = await fetchWithRetry("https://example.test/flaky", {
      baseDelayMs: 1,
    });
    expect(res.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("respects maxRetries (3 attempts → ServerError)", async () => {
    fetchSpy
      .mockResolvedValue(makeResponse(503))
      .mockResolvedValueOnce(makeResponse(503))
      .mockResolvedValueOnce(makeResponse(503))
      .mockResolvedValueOnce(makeResponse(503));
    await expect(
      fetchWithRetry("https://example.test/down", { baseDelayMs: 1, maxRetries: 3 }),
    ).rejects.toBeInstanceOf(ServerError);
    expect(fetchSpy).toHaveBeenCalledTimes(3);
  });

  it("after retry-budget exhaustion on 429 throws RateLimitError with retryAfter", async () => {
    // Use retry-after: 0 so retry sleeps are instant; the FINAL thrown error
    // still picks up retryAfter from the last response's header (and would
    // honour a larger value at the throw site too).
    fetchSpy.mockImplementation(
      async () =>
        new Response("", {
          status: 429,
          headers: { "retry-after": "0" },
        }),
    );
    await expect(
      fetchWithRetry("https://example.test/lim", { baseDelayMs: 1, maxRetries: 3 }),
    ).rejects.toMatchObject({
      name: "RateLimitError",
      statusCode: 429,
      retryAfter: 0,
    });
  });
});

describe("fetchWithRetry — non-retryable 4xx", () => {
  it("404 → NotFoundError (no retry)", async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(404));
    await expect(fetchWithRetry("https://example.test/nf")).rejects.toBeInstanceOf(NotFoundError);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("400 → ValidationError", async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(400));
    await expect(fetchWithRetry("https://example.test/bad")).rejects.toBeInstanceOf(
      ValidationError,
    );
  });

  it("401 → AuthenticationError", async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(401));
    await expect(fetchWithRetry("https://example.test/auth")).rejects.toBeInstanceOf(
      AuthenticationError,
    );
  });

  it("403 → ForbiddenError", async () => {
    fetchSpy.mockResolvedValueOnce(makeResponse(403));
    await expect(fetchWithRetry("https://example.test/forbidden")).rejects.toBeInstanceOf(
      ForbiddenError,
    );
  });
});

describe("fetchWithRetry — abort + timeout", () => {
  it("honors caller AbortSignal", async () => {
    const controller = new AbortController();
    fetchSpy.mockImplementation(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          const sig = (init as RequestInit | undefined)?.signal;
          if (sig?.aborted) {
            reject(new DOMException("Aborted", "AbortError"));
            return;
          }
          sig?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        }),
    );
    const p = fetchWithRetry("https://example.test/slow", {
      signal: controller.signal,
      baseDelayMs: 1,
    });
    controller.abort();
    await expect(p).rejects.toBeInstanceOf(DOMException);
  });

  it("triggers per-attempt timeout via TherminalError after retries exhausted", async () => {
    // Simulate fetch that respects the per-attempt AbortController by rejecting
    // with AbortError as soon as the signal aborts.
    fetchSpy.mockImplementation(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          const sig = (init as RequestInit | undefined)?.signal;
          sig?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }),
    );
    await expect(
      fetchWithRetry("https://example.test/timeout", {
        baseDelayMs: 1,
        maxRetries: 2,
        timeoutMs: 5,
      }),
    ).rejects.toBeInstanceOf(TherminalError);
  });
});

describe("fetchWithRetry — retry-after header parsing", () => {
  it("honors numeric retry-after on retryable status", async () => {
    let calls = 0;
    fetchSpy.mockImplementation(async () => {
      calls += 1;
      if (calls === 1) {
        return new Response("", { status: 503, headers: { "retry-after": "0" } });
      }
      return makeResponse(200, "ok");
    });
    const res = await fetchWithRetry("https://example.test/ra", { baseDelayMs: 1 });
    expect(res.status).toBe(200);
    expect(calls).toBe(2);
  });
});
