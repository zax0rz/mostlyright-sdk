import { describe, expect, it, vi } from "vitest";

import { fetchEventById } from "../../src/polymarket/index.js";

describe("fetchEventById", () => {
  it("returns the event JSON on 200 (via fetchFn override)", async () => {
    const fetchFn = vi.fn(
      async () =>
        new Response(JSON.stringify({ id: "evt-abc", slug: "x" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const ev = await fetchEventById("evt-abc", { fetchFn });
    expect(ev?.id).toBe("evt-abc");
  });

  it("returns null on 404 via fetchFn override (resp.status === 404 path)", async () => {
    const fetchFn = vi.fn(async () => new Response("Not Found", { status: 404 }));
    const ev = await fetchEventById("missing-evt", { fetchFn });
    expect(ev).toBeNull();
  });

  it("returns null when fetchWithRetry throws NotFoundError (codex iter-2 P2)", async () => {
    // Simulate the default path: import fetchWithRetry's NotFoundError and
    // throw it. The override here mocks fetchWithRetry's BEHAVIOR rather
    // than a Response, so we exercise the catch branch even from a fetchFn
    // override (acceptable: the catch handles whatever throws).
    const fetchFn = vi.fn(async () => {
      const { NotFoundError } = await import("@mostlyright/core");
      throw new NotFoundError("simulated 404");
    });
    const ev = await fetchEventById("missing-evt", { fetchFn });
    expect(ev).toBeNull();
  });
});
