// Structured exception hierarchy for the mostlyright TS SDK.
//
// Mirrors the Python design in `packages/core/src/mostlyright/core/exceptions.py`
// and `packages/core/src/mostlyright/_internal/exceptions.py`. Every error
// subclasses `TradewindsError` and exposes a `toDict()` method that returns a
// JSON-safe payload suitable for MCP `error.data` / extension messaging.
//
// Role-name vocabulary for SourceMismatchError matches Python:
//   "observations" / "forecasts" / "settlement"  (long form, NOT the col prefixes)

// ---------------------------------------------------------------------------
// JSON-safe coercion (mirrors `mostlyright.core._json_safe.to_json_safe`)
// ---------------------------------------------------------------------------

/**
 * Recursively coerce `value` into a JSON-serializable structure.
 *
 * Coercion rules (mirrors Python's `to_json_safe`):
 *  - `null` / `undefined` / `NaN` / `Infinity` / `-Infinity` → `null`
 *  - `Date` → ISO 8601 UTC string ending in `Z`
 *  - Numeric / boolean / string scalars pass through (non-finite numbers → null)
 *  - Arrays + plain objects → recursive (cycles → `{ _cycle: true, value: String(obj) }`)
 *  - Dict keys MUST be strings; non-string keys throw `TypeError`.
 *  - Anything else (Symbol, function, class instance without `toJSON`) →
 *    `{ _repr_only: true, value: String(value) }`.
 */
export function toJsonSafe(value: unknown, seen?: WeakSet<object>): unknown {
  const visited = seen ?? new WeakSet<object>();

  // null / undefined → null
  if (value === null || value === undefined) {
    return null;
  }

  // Booleans pass through.
  if (typeof value === "boolean") {
    return value;
  }

  // Strings pass through.
  if (typeof value === "string") {
    return value;
  }

  // Numbers — non-finite (NaN, +/-Infinity) coerce to null.
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  // bigint → number when safe, else stringify (JSON can't natively encode bigint).
  if (typeof value === "bigint") {
    // Match Python: integers pass through as native numeric. Safe-range only.
    if (value >= BigInt(Number.MIN_SAFE_INTEGER) && value <= BigInt(Number.MAX_SAFE_INTEGER)) {
      return Number(value);
    }
    return { _repr_only: true, value: value.toString() };
  }

  // Date → ISO 8601 UTC string (always ending in "Z").
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      return null;
    }
    return value.toISOString();
  }

  // Arrays — recurse, track cycles.
  if (Array.isArray(value)) {
    if (visited.has(value)) {
      return { _cycle: true, value: String(value) };
    }
    visited.add(value);
    try {
      return value.map((item) => toJsonSafe(item, visited));
    } finally {
      visited.delete(value);
    }
  }

  // Plain objects — recurse, track cycles, enforce string keys.
  if (typeof value === "object") {
    if (visited.has(value as object)) {
      return { _cycle: true, value: String(value) };
    }
    visited.add(value as object);
    try {
      const out: Record<string, unknown> = {};
      for (const key of Object.keys(value as Record<string, unknown>)) {
        if (typeof key !== "string") {
          throw new TypeError(`toJsonSafe dict keys must be string; got ${typeof key}`);
        }
        out[key] = toJsonSafe((value as Record<string, unknown>)[key], visited);
      }
      return out;
    } finally {
      visited.delete(value as object);
    }
  }

  // Symbols, functions, etc. — repr-only marker.
  return { _repr_only: true, value: String(value) };
}

// ---------------------------------------------------------------------------
// Base class
// ---------------------------------------------------------------------------

export interface TradewindsErrorOptions {
  errorCode?: string;
  source?: string | null;
  requestId?: string | null;
}

/**
 * Base class for all mostlyright structured errors.
 *
 * `errorCode` is a stable enum (e.g. "SOURCE_UNAVAILABLE") used by callers /
 * agents to branch on without parsing message text. `source` is the source id
 * involved (e.g. "iem.archive") when applicable, and `requestId` correlates a
 * JSON-RPC / MCP request id when applicable.
 */
export class TradewindsError extends Error {
  /** Subclass override — the stable string enum surfaced via `errorCode`. */
  static defaultErrorCode = "TRADEWINDS_ERROR";

  readonly errorCode: string;
  readonly source: string | null;
  readonly requestId: string | null;

  constructor(message = "", options: TradewindsErrorOptions = {}) {
    super(message);
    this.name = new.target.name;
    const ctor = this.constructor as typeof TradewindsError;
    this.errorCode = options.errorCode ?? ctor.defaultErrorCode;
    this.source = options.source ?? null;
    this.requestId = options.requestId ?? null;
    // Restore prototype chain after `Error` (needed for `instanceof` across
    // transpilation / ES5 targets).
    Object.setPrototypeOf(this, new.target.prototype);
  }

  /**
   * Subclass hook returning the structured attributes for `toDict`.
   * Values are passed through `toJsonSafe` by `toDict()`, so subclasses
   * don't need to coerce values themselves.
   */
  protected payload(): Record<string, unknown> {
    return {
      error_code: this.errorCode,
      message: this.message,
      source: this.source,
      request_id: this.requestId,
    };
  }

  /** Return a JSON-safe dict suitable for MCP `error.data`. */
  toDict(): Record<string, unknown> {
    const safe = toJsonSafe(this.payload());
    return safe as Record<string, unknown>;
  }
}

// ---------------------------------------------------------------------------
// SourceUnavailableError
// ---------------------------------------------------------------------------

export interface SourceUnavailableErrorOptions extends TradewindsErrorOptions {
  httpStatus?: number | null;
  retryable?: boolean;
  retryAfterS?: number | null;
  underlying?: string;
  url?: string | null;
}

export class SourceUnavailableError extends TradewindsError {
  static override defaultErrorCode = "SOURCE_UNAVAILABLE";

  readonly httpStatus: number | null;
  readonly retryable: boolean;
  readonly retryAfterS: number | null;
  readonly underlying: string;
  readonly url: string | null;

  constructor(message = "", options: SourceUnavailableErrorOptions = {}) {
    super(message, options);
    this.httpStatus = options.httpStatus ?? null;
    this.retryable = options.retryable ?? false;
    this.retryAfterS = options.retryAfterS ?? null;
    this.underlying = options.underlying ?? "";
    this.url = options.url ?? null;
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      http_status: this.httpStatus,
      retryable: this.retryable,
      retry_after_s: this.retryAfterS,
      underlying: this.underlying,
      url: this.url,
    };
  }
}

// ---------------------------------------------------------------------------
// DataAvailabilityError (Phase 21 21-09)
// ---------------------------------------------------------------------------
//
// Typed exception for "I tried to fetch and got nothing usable" — replaces
// 3+ overloaded SourceUnavailableError sites where consumers had to parse
// message strings to differentiate (rate-limit retry vs model-unavailable
// hard-fail vs cache-miss re-fetch). The reason enum is shared lockstep
// with Python (`mostlyright.core.exceptions.DataAvailabilityError`); drift
// is the load-bearing risk.

/** Shared reason enum — MUST match Python EXACTLY (Phase 21 D-04). */
export const DATA_AVAILABILITY_REASONS = [
  "model_unavailable",
  "out_of_window",
  "cache_miss",
  "source_404",
  "source_5xx",
  "rate_limited",
] as const;

export type DataAvailabilityReason = (typeof DATA_AVAILABILITY_REASONS)[number];

export interface DataAvailabilityErrorOptions extends TradewindsErrorOptions {
  reason: DataAvailabilityReason;
  hint: string;
}

export class DataAvailabilityError extends TradewindsError {
  static override defaultErrorCode = "DATA_AVAILABILITY";

  readonly reason: DataAvailabilityReason;
  readonly hint: string;

  constructor(options: DataAvailabilityErrorOptions) {
    if (!DATA_AVAILABILITY_REASONS.includes(options.reason)) {
      throw new RangeError(
        `DataAvailabilityError: unknown reason "${String(options.reason)}". ` +
          `Valid reasons: ${DATA_AVAILABILITY_REASONS.join(", ")}`,
      );
    }
    if (typeof options.hint !== "string" || options.hint.length === 0) {
      throw new TypeError("DataAvailabilityError: hint is required and must be a non-empty string");
    }
    const message = `[${options.reason}] ${options.hint}`;
    super(message, options);
    this.reason = options.reason;
    this.hint = options.hint;
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      reason: this.reason,
      hint: this.hint,
    };
  }
}

// ---------------------------------------------------------------------------
// NwpNotAvailableError (Post-21-07 follow-up)
// ---------------------------------------------------------------------------
//
// Subclass of DataAvailabilityError raised when the TS `forecastNwp()` stub
// is called. Phase 21 21-07 routes the generic stub error through
// DataAvailabilityError; this dedicated subclass adds:
//
//   1. instanceof-based dispatch — `catch (e) { if (e instanceof
//      NwpNotAvailableError) ... }` is cleaner than `e.reason ===
//      "model_unavailable" && e.source === "nwp-stub"`.
//   2. IDE autocomplete on `.model` + `.station` — narrows the payload so
//      consumers don't have to parse `e.hint` to retrieve them.
//   3. A typed compile-time signal: `forecastNwp()` returns
//      `Promise<never>`, but the throw site declares `@throws
//      NwpNotAvailableError` so JSDoc tooling surfaces the deferral up-front.
//
// Back-compat: NwpNotAvailableError IS-A DataAvailabilityError with
// reason="model_unavailable", so existing `catch (e) { if (e instanceof
// DataAvailabilityError && e.reason === "model_unavailable") ... }` paths
// continue to work unchanged.

export interface NwpNotAvailableErrorOptions extends TradewindsErrorOptions {
  /** Station the caller asked for (echoed back for log/error attribution). */
  station: string;
  /** NWP model the caller asked for (e.g. `"gfs"`, `"hrrr"`). */
  model: string;
  /** Operator-actionable hint. Required (matches DataAvailabilityError contract). */
  hint: string;
}

/**
 * Raised when the TS `forecastNwp()` stub is called.
 *
 * **Why this exists:** no production-ready browser GRIB2 decoder ships in
 * v1.x (eccodes / cfgrib are C/Python only; WASM compile-time + bundle
 * size make a browser port impractical today). The function signature is
 * stable so callers can write code today; v2.0+ lands the execution body.
 *
 * **Recommended catch pattern:**
 *
 * ```ts
 * import { forecastNwp } from '@mostlyrightmd/weather';
 * import { NwpNotAvailableError } from '@mostlyrightmd/core';
 *
 * try {
 *   const grid = await forecastNwp('KNYC', 'gfs');
 * } catch (e) {
 *   if (e instanceof NwpNotAvailableError) {
 *     console.warn(`NWP deferred to v2.0+; ${e.hint}`);
 *     // Fall back to iemMosForecasts() when available, else Python SDK.
 *   } else {
 *     throw e;
 *   }
 * }
 * ```
 *
 * See [docs/nwp-forecasts.md](https://mostlyright.md/docs/sdk/typescript/nwp-forecasts/)
 * for the full architectural rationale and the v2.0+ roadmap.
 */
export class NwpNotAvailableError extends DataAvailabilityError {
  static override defaultErrorCode = "NWP_NOT_AVAILABLE";

  readonly station: string;
  readonly model: string;

  constructor(options: NwpNotAvailableErrorOptions) {
    // exactOptionalPropertyTypes: true — only include requestId when the
    // caller passed a non-undefined value. Passing `requestId: undefined`
    // explicitly would type-error against the parent's narrower contract.
    const parentOpts: DataAvailabilityErrorOptions = {
      reason: "model_unavailable",
      hint: options.hint,
      source: options.source ?? `nwp.${options.model}`,
    };
    if (options.requestId !== undefined && options.requestId !== null) {
      parentOpts.requestId = options.requestId;
    }
    super(parentOpts);
    this.station = options.station;
    this.model = options.model;
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      station: this.station,
      model: this.model,
    };
  }
}

// ---------------------------------------------------------------------------
// SchemaValidationError
// ---------------------------------------------------------------------------

export interface SchemaValidationErrorOptions extends TradewindsErrorOptions {
  schemaId: string;
  violations?: Array<Record<string, unknown>>;
  quarantineCount?: number;
  sampleViolations?: Array<Record<string, unknown>>;
}

export class SchemaValidationError extends TradewindsError {
  static override defaultErrorCode = "SCHEMA_VALIDATION_FAILED";

  readonly schemaId: string;
  readonly violations: Array<Record<string, unknown>>;
  readonly quarantineCount: number;
  readonly sampleViolations: Array<Record<string, unknown>>;

  constructor(message: string, options: SchemaValidationErrorOptions) {
    super(message, options);
    this.schemaId = options.schemaId;
    this.violations = [...(options.violations ?? [])];
    this.quarantineCount = options.quarantineCount ?? 0;
    this.sampleViolations = [...(options.sampleViolations ?? [])];
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      schema_id: this.schemaId,
      violations: this.violations,
      quarantine_count: this.quarantineCount,
      sample_violations: this.sampleViolations,
    };
  }
}

// ---------------------------------------------------------------------------
// SourceMismatchError
// ---------------------------------------------------------------------------

export type SourceMismatchRole = "observations" | "forecasts" | "settlement";

export interface SourceMismatchErrorOptions extends TradewindsErrorOptions {
  schemaSource: string;
  dataSource: string;
  role?: SourceMismatchRole | null;
  catalogWarning?: string | null;
}

export class SourceMismatchError extends TradewindsError {
  static override defaultErrorCode = "SOURCE_MISMATCH";

  /** Canonical role-name vocabulary (design.md §R). */
  static readonly VALID_ROLES: ReadonlySet<SourceMismatchRole> = new Set([
    "observations",
    "forecasts",
    "settlement",
  ]);

  readonly schemaSource: string;
  readonly dataSource: string;
  readonly role: SourceMismatchRole | null;
  readonly catalogWarning: string | null;

  constructor(message: string, options: SourceMismatchErrorOptions) {
    super(message, options);
    this.schemaSource = options.schemaSource;
    this.dataSource = options.dataSource;
    this.role = options.role ?? null;
    this.catalogWarning = options.catalogWarning ?? null;
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      schema_source: this.schemaSource,
      data_source: this.dataSource,
      role: this.role,
      catalog_warning: this.catalogWarning,
    };
  }
}

// ---------------------------------------------------------------------------
// LeakageError
// ---------------------------------------------------------------------------

export interface LeakageErrorOptions extends TradewindsErrorOptions {
  asOf: string;
  violatingCount: number;
  sampleViolations?: Array<Record<string, unknown>>;
}

export class LeakageError extends TradewindsError {
  static override defaultErrorCode = "LEAKAGE_DETECTED";

  readonly asOf: string;
  readonly violatingCount: number;
  readonly sampleViolations: Array<Record<string, unknown>>;

  constructor(message: string, options: LeakageErrorOptions) {
    super(message, options);
    this.asOf = options.asOf;
    this.violatingCount = options.violatingCount;
    this.sampleViolations = [...(options.sampleViolations ?? [])];
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      as_of: this.asOf,
      violating_count: this.violatingCount,
      sample_violations: this.sampleViolations,
    };
  }
}

// ---------------------------------------------------------------------------
// TemporalDriftError
// ---------------------------------------------------------------------------

export interface TemporalDriftErrorOptions extends TradewindsErrorOptions {
  schemaId: string;
  assertedRange: [string, string];
  violatingRows: number;
  sampleViolations?: Array<Record<string, unknown>>;
}

export class TemporalDriftError extends TradewindsError {
  static override defaultErrorCode = "TEMPORAL_DRIFT";

  readonly schemaId: string;
  readonly assertedRange: [string, string];
  readonly violatingRows: number;
  readonly sampleViolations: Array<Record<string, unknown>>;

  constructor(message: string, options: TemporalDriftErrorOptions) {
    super(message, options);
    this.schemaId = options.schemaId;
    this.assertedRange = [options.assertedRange[0], options.assertedRange[1]];
    this.violatingRows = options.violatingRows;
    this.sampleViolations = [...(options.sampleViolations ?? [])];
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      schema_id: this.schemaId,
      asserted_range: [this.assertedRange[0], this.assertedRange[1]],
      violating_rows: this.violatingRows,
      sample_violations: this.sampleViolations,
    };
  }
}

// ---------------------------------------------------------------------------
// PayloadTooLargeError
// ---------------------------------------------------------------------------

export interface PayloadTooLargeErrorOptions extends TradewindsErrorOptions {
  declaredSize: number;
  limit: number;
  acceptedModes?: string[];
}

export class PayloadTooLargeError extends TradewindsError {
  static override defaultErrorCode = "PAYLOAD_TOO_LARGE";

  readonly declaredSize: number;
  readonly limit: number;
  readonly acceptedModes: string[];

  constructor(message: string, options: PayloadTooLargeErrorOptions) {
    super(message, options);
    this.declaredSize = options.declaredSize;
    this.limit = options.limit;
    this.acceptedModes = [...(options.acceptedModes ?? [])];
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      declared_size: this.declaredSize,
      limit: this.limit,
      accepted_modes: this.acceptedModes,
    };
  }
}

// ---------------------------------------------------------------------------
// DeferredMarketError (TS-W6 placeholder; mirrors mostlyright.international)
// ---------------------------------------------------------------------------

export class DeferredMarketError extends TradewindsError {
  static override defaultErrorCode = "DEFERRED_MARKET";
}

// ---------------------------------------------------------------------------
// PolymarketEventError (TS-W5 placeholder; mirrors mostlyright.markets.polymarket)
// ---------------------------------------------------------------------------

export class PolymarketEventError extends TradewindsError {
  static override defaultErrorCode = "POLYMARKET_EVENT_INVALID";
}

// ---------------------------------------------------------------------------
// HTTP-layer hierarchy (mirrors mostlyright._internal.exceptions)
// ---------------------------------------------------------------------------

export interface TherminalErrorOptions extends TradewindsErrorOptions {
  statusCode?: number | null;
  retryAfter?: number | null;
}

/**
 * Base HTTP-layer marker. Subclass of `TradewindsError` so callers that
 * catch `TradewindsError` also catch transport errors.
 */
export class TherminalError extends TradewindsError {
  static override defaultErrorCode = "HTTP_ERROR";

  readonly statusCode: number | null;

  constructor(message: string, options: TherminalErrorOptions = {}) {
    super(message, options);
    this.statusCode = options.statusCode ?? null;
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      status_code: this.statusCode,
    };
  }
}

export class NotFoundError extends TherminalError {
  static override defaultErrorCode = "HTTP_NOT_FOUND";

  constructor(message = "Resource not found", options: TherminalErrorOptions = {}) {
    super(message, { ...options, statusCode: options.statusCode ?? 404 });
  }
}

export interface RateLimitErrorOptions extends TherminalErrorOptions {
  retryAfter?: number | null;
}

export class RateLimitError extends TherminalError {
  static override defaultErrorCode = "HTTP_RATE_LIMITED";

  readonly retryAfter: number | null;

  constructor(retryAfter: number | null = 1, options: RateLimitErrorOptions = {}) {
    const msg = `Rate limit exceeded. Retry after ${retryAfter ?? "?"}s`;
    super(msg, { ...options, statusCode: options.statusCode ?? 429 });
    this.retryAfter = retryAfter;
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      retry_after: this.retryAfter,
    };
  }
}

export class ValidationError extends TherminalError {
  static override defaultErrorCode = "HTTP_BAD_REQUEST";

  constructor(message = "Invalid request", options: TherminalErrorOptions = {}) {
    super(message, { ...options, statusCode: options.statusCode ?? 400 });
  }
}

export class AuthenticationError extends TherminalError {
  static override defaultErrorCode = "HTTP_UNAUTHORIZED";

  constructor(message = "Authentication required", options: TherminalErrorOptions = {}) {
    super(message, { ...options, statusCode: options.statusCode ?? 401 });
  }
}

export class ForbiddenError extends TherminalError {
  static override defaultErrorCode = "HTTP_FORBIDDEN";

  constructor(message = "Access denied", options: TherminalErrorOptions = {}) {
    super(message, { ...options, statusCode: options.statusCode ?? 403 });
  }
}

export class ServerError extends TherminalError {
  static override defaultErrorCode = "HTTP_SERVER_ERROR";

  constructor(message = "Server error", options: TherminalErrorOptions = {}) {
    super(message, { ...options, statusCode: options.statusCode ?? 500 });
  }
}

// ---------------------------------------------------------------------------
// LiveStreamError + NoLiveDataError (Phase 11)
// ---------------------------------------------------------------------------

/**
 * Base class for `mostlyright.live.stream` / `live.latest` failures.
 *
 * Mirrors Python `LiveStreamError`. Live-streaming errors are a separate
 * sub-tree from `SourceUnavailableError` because the recovery path differs —
 * `stream()` swallows empty-tick errors and waits for the next polite-floor
 * cycle. Only `latest()` raises `NoLiveDataError` on empty responses.
 */
export class LiveStreamError extends TradewindsError {
  static override defaultErrorCode = "LIVE_STREAM_ERROR";
}

export interface NoLiveDataErrorOptions extends TradewindsErrorOptions {
  station: string;
  source: string;
}

/**
 * `mostlyright.live.latest` returned no observations for the station.
 *
 * Carries the resolved ICAO `station` and the canonical source identity
 * tag (`"awc.live"` / `"iem.live"`) so caller logs can branch by source
 * without re-parsing the message.
 */
export class NoLiveDataError extends LiveStreamError {
  static override defaultErrorCode = "NO_LIVE_DATA";

  readonly station: string;

  constructor(message: string, options: NoLiveDataErrorOptions) {
    super(message, { ...options, source: options.source });
    this.station = options.station;
  }

  protected override payload(): Record<string, unknown> {
    return {
      ...super.payload(),
      station: this.station,
    };
  }
}
