// TOON v3.0 tabular format — byte-equivalent to Python `encode_tabular`.
//
// Ports the encoder portions of
// `packages/core/src/tradewinds/core/formats/_toon.py` and the tabular
// loader from `packages/core/src/tradewinds/core/formats/toon.py`.
//
// Wire shape (single tabular block):
//
//     rows[N]{col1,col2,col3}:
//       v1a,v2a,v3a
//       v1b,v2b,v3b
//
// Where N is the row count, `{...}` is the column list, each subsequent line
// is one row's values. Column order comes from the first row's keys.
//
// TOON loss matrix (matches Python `toon.py`):
//   - dict/object cells stringify deterministically via canonical JSON
//     (sorted keys + JSON.stringify of nested values).
//   - null + undefined both encode as the bare literal `null`.
//   - NaN / +Infinity / -Infinity encode as `null` (per `_format_number`).
//   - Integer-valued floats serialize without a fractional part (1.0 → "1").
//   - Strings that look numeric, start with - / + / digit, are
//     `true`/`false`/`null`, or contain commas/quotes/control chars are
//     quoted. Otherwise emitted bare.

// ---------------------------------------------------------------------------
// Encoder regex set (mirrors Python `_toon.py`)
// ---------------------------------------------------------------------------

const SAFE_KEY_RE = /^[A-Za-z_][A-Za-z0-9_.]*$/;
const NUMERIC_LIKE_RE = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
// Quote triggers per TOON spec: colon, quote, backslash, brackets, braces,
// ASCII control chars, NEL, LSEP, PSEP. Constructed via RegExp(...) to avoid
// embedding literal LSEP/PSEP bytes (esbuild rejects those in regex literals).
// biome-ignore lint/suspicious/noControlCharactersInRegex: TOON spec parity
const NEEDS_QUOTE_CHARS_RE = /[:\\\"'\[\]{}\x00-\x1f\x7f\x85\u2028\u2029]/;
// Control chars without a defined TOON escape — stripped on quote.
// biome-ignore lint/suspicious/noControlCharactersInRegex: TOON spec parity
const UNSUPPORTED_CTRL_RE = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x85\u2028\u2029]/g;

// ---------------------------------------------------------------------------
// Scalar encoding
// ---------------------------------------------------------------------------

function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return "null";
  if (n === 0) return "0"; // collapses -0 to "0"
  if (Number.isInteger(n) && Math.abs(n) <= 2 ** 53) return String(n);
  let s = String(n);
  // Expand scientific notation to plain decimal. Python uses Decimal —
  // we use toFixed where possible, falling back to toPrecision-based logic.
  if (/[eE]/.test(s)) {
    // toFixed/toPrecision don't fully match Python's Decimal expansion at
    // extreme values, but for the values realistically in weather data
    // (temperatures, lat/lng) String(n) returns plain decimal already.
    // For extreme cases, fall back to a manual expansion.
    s = expandExponent(s);
  }
  return s;
}

function expandExponent(s: string): string {
  const m = /^(-?)(\d+(?:\.\d+)?)[eE]([+-]?\d+)$/.exec(s);
  if (!m) return s;
  const sign = m[1] ?? "";
  const mantissa = m[2] ?? "";
  const exp = Number(m[3]);
  const [intPart, fracPart = ""] = mantissa.split(".");
  const digits = (intPart ?? "") + fracPart;
  const pointPos = (intPart ?? "").length + exp;
  let out: string;
  if (pointPos <= 0) {
    out = `0.${"0".repeat(-pointPos)}${digits}`.replace(/0+$/, "");
    if (out.endsWith(".")) out = out.slice(0, -1);
  } else if (pointPos >= digits.length) {
    out = digits + "0".repeat(pointPos - digits.length);
  } else {
    out = `${digits.slice(0, pointPos)}.${digits.slice(pointPos)}`.replace(/0+$/, "");
    if (out.endsWith(".")) out = out.slice(0, -1);
  }
  return sign + out;
}

function needsQuoting(s: string, delimiter: string): boolean {
  if (s.length === 0) return true;
  const first = s.charAt(0);
  const last = s.charAt(s.length - 1);
  if (first === " " || first === "\t") return true;
  if (last === " " || last === "\t") return true;
  if (s === "true" || s === "false" || s === "null") return true;
  if (first === "-" || first === "+") return true;
  if (first >= "0" && first <= "9") return true;
  if (NUMERIC_LIKE_RE.test(s)) return true;
  if (s.includes(delimiter)) return true;
  if (NEEDS_QUOTE_CHARS_RE.test(s)) return true;
  return false;
}

function quoteString(s: string): string {
  // Strip unsupported control chars first (matches Python — no escape
  // sequence exists for them).
  let out = s.replace(UNSUPPORTED_CTRL_RE, "");
  out = out.replace(/\\/g, "\\\\");
  out = out.replace(/"/g, '\\"');
  out = out.replace(/\n/g, "\\n");
  out = out.replace(/\r/g, "\\r");
  out = out.replace(/\t/g, "\\t");
  return `"${out}"`;
}

function formatKey(key: string): string {
  if (typeof key !== "string") {
    throw new TypeError(`TOON keys must be strings; got ${typeof key}`);
  }
  if (SAFE_KEY_RE.test(key)) return key;
  return quoteString(key);
}

function encodeScalar(value: unknown, delimiter: string): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return formatNumber(value);
  if (typeof value === "string") {
    if (needsQuoting(value, delimiter)) return quoteString(value);
    return value;
  }
  // Objects / arrays / etc. — canonical JSON (sorted keys) for parity with
  // Python `_coerce_cell` dict-handling, otherwise String(value).
  if (typeof value === "object") {
    if (Array.isArray(value)) {
      return quoteString(JSON.stringify(value));
    }
    // Sorted-key JSON for determinism (matches Python json.dumps sort_keys).
    const sorted = sortedJson(value as Record<string, unknown>);
    return quoteString(sorted);
  }
  return quoteString(String(value));
}

function sortedJson(obj: Record<string, unknown>): string {
  const keys = Object.keys(obj).sort();
  const parts = keys.map((k) => `${JSON.stringify(k)}:${JSON.stringify(obj[k])}`);
  return `{${parts.join(",")}}`;
}

// ---------------------------------------------------------------------------
// Tabular validation (mirrors Python `_is_tabular`)
// ---------------------------------------------------------------------------

/**
 * Thrown when {@link toonDumps} receives rows that aren't valid tabular
 * input. Mirrors the Python `encode_tabular` `ValueError` — the encoder
 * MUST refuse non-uniform rows or non-primitive values rather than
 * silently dropping columns or stringifying nested structures.
 *
 * Iter-1 C3: the previous TS encoder used `Object.keys(rows[0])` and
 * encoded every subsequent row through that column list — meaning rows
 * with extra keys had them dropped, rows missing a first-row key got a
 * silent `null`, and rows with object/array values stringified via
 * `JSON.stringify` (also silent). All three are data corruption when the
 * caller didn't realize their rows weren't uniform.
 */
export class ToonTabularError extends RangeError {
  override name = "ToonTabularError";
}

function isToonPrimitive(v: unknown): boolean {
  // Python `_is_tabular` accepts None / str / int / float / bool. The TS
  // analog: null/undefined (both encode as `null`), string, finite or
  // non-finite number (NaN/Inf encode as `null` via formatNumber),
  // boolean. Anything else (object, array, function, symbol, bigint) is
  // non-tabular.
  if (v === null || v === undefined) return true;
  const t = typeof v;
  return t === "string" || t === "number" || t === "boolean";
}

function assertTabular(rows: ReadonlyArray<Record<string, unknown>>): void {
  if (rows.length === 0) return;
  const first = rows[0] as Record<string, unknown>;
  const expectedKeys = Object.keys(first);
  if (expectedKeys.length === 0) {
    throw new ToonTabularError(
      "toonDumps requires non-empty rows; first row has no keys (Python parity: encode_tabular rejects empty key set)",
    );
  }
  const expectedKeySet = new Set(expectedKeys);
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i] as Record<string, unknown>;
    const rowKeys = Object.keys(row);
    // (a) Key-set equality. Python compares `set(item.keys()) != key_set`.
    if (rowKeys.length !== expectedKeySet.size) {
      throw new ToonTabularError(
        `toonDumps requires uniform rows; row ${i} has ${rowKeys.length} key(s) vs row 0's ${expectedKeySet.size}. Python encode_tabular rejects rows whose key sets differ.`,
      );
    }
    for (const k of rowKeys) {
      if (!expectedKeySet.has(k)) {
        throw new ToonTabularError(
          `toonDumps requires uniform rows; row ${i} has key ${JSON.stringify(k)} not present in row 0. Python encode_tabular rejects rows whose key sets differ.`,
        );
      }
    }
    // (b) Value primitivity. Python check: `v is None or isinstance(v, str|int|float|bool)`.
    for (const k of expectedKeys) {
      const v = row[k];
      if (!isToonPrimitive(v)) {
        throw new ToonTabularError(
          `toonDumps requires primitive cell values; row ${i} column ${JSON.stringify(k)} has non-primitive value of type ${typeof v}. Python encode_tabular rejects nested objects/arrays at the cell level.`,
        );
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Public encoder
// ---------------------------------------------------------------------------

/**
 * Encode rows as a TOON v3.0 tabular block.
 *
 * Header is `rows[N]{c1,c2,...}:`; data lines are 2-space indented and
 * comma-separated. Empty rows emits `rows[0]:` (header-only, no columns
 * region; matches Python `_encode_array_field` empty-list path).
 *
 * Note: empty-row encoding differs from `dumps()` in `toon.py` (which
 * carries column names through `rows[0]{...}:`). The TS encoder accepts
 * a `columns` second arg in the empty case for parity with that
 * pandas-aware wrapper.
 *
 * @throws {ToonTabularError} when rows are non-uniform (differing key
 *   sets across rows) or when any cell value is non-primitive
 *   (object/array/bigint/etc.). Mirrors Python `encode_tabular`'s
 *   `ValueError`. Iter-1 C3 fix.
 */
export function toonDumps(
  rows: ReadonlyArray<Record<string, unknown>>,
  columns?: ReadonlyArray<string>,
): string {
  if (rows.length === 0) {
    // Empty-frame: carry column names if provided (matches the Python
    // DataFrame wrapper's `rows[0]{...}:` empty form). Otherwise emit the
    // bare encoder form.
    if (columns !== undefined) {
      const cols = columns.map((c) => formatKey(String(c))).join(",");
      return `rows[0]{${cols}}:`;
    }
    return "rows[0]:";
  }
  // C3 hard gate: refuse non-uniform rows BEFORE looking at row 0's keys
  // for the column header. Otherwise we'd silently drop extra columns or
  // null-fill missing ones.
  assertTabular(rows);
  const cols = Object.keys(rows[0] as Record<string, unknown>);
  const colHeader = cols.map((c) => formatKey(c)).join(",");
  const header = `rows[${rows.length}]{${colHeader}}:`;
  const dataLines = rows.map((r) => {
    const vals = cols.map((c) => encodeScalar((r as Record<string, unknown>)[c], ","));
    return `  ${vals.join(",")}`;
  });
  return `${header}\n${dataLines.join("\n")}`;
}

// ---------------------------------------------------------------------------
// Decoder
// ---------------------------------------------------------------------------

const HEADER_PREFIX_RE = /^(?<key>[A-Za-z_][A-Za-z0-9_.]*)\[(?<count>\d+)\]/;

function parseHeaderLine(line: string): { count: number; cols: string } {
  const prefix = HEADER_PREFIX_RE.exec(line);
  if (prefix == null) {
    throw new RangeError(`TOON payload missing tabular header; got: ${JSON.stringify(line)}`);
  }
  const declared = Number(prefix.groups?.count ?? "");
  let i = prefix[0].length;
  const n = line.length;
  // Handle the header-only empty form: `rows[0]:` (no `{cols}` region).
  if (i < n && line[i] === ":" && declared === 0) {
    const rest = line.slice(i + 1).trim();
    if (rest === "") return { count: 0, cols: "" };
    throw new RangeError(`TOON header has trailing junk: ${JSON.stringify(line)}`);
  }
  if (i >= n || line[i] !== "{") {
    throw new RangeError(`TOON header missing column region: ${JSON.stringify(line)}`);
  }
  i++; // consume `{`
  // Walk to matching `}` honoring quoted strings.
  while (i < n) {
    const ch = line[i];
    if (ch === '"') {
      let j = i + 1;
      while (j < n) {
        if (line[j] === "\\" && j + 1 < n) {
          j += 2;
          continue;
        }
        if (line[j] === '"') break;
        j++;
      }
      if (j >= n) {
        throw new RangeError(
          `TOON header has unterminated quoted column name: ${JSON.stringify(line)}`,
        );
      }
      i = j + 1;
      continue;
    }
    if (ch === "}") break;
    i++;
  }
  if (i >= n || line[i] !== "}") {
    throw new RangeError(`TOON header missing closing brace: ${JSON.stringify(line)}`);
  }
  const cols = line.slice(prefix[0].length + 1, i);
  const rest = line.slice(i + 1).trim();
  if (rest !== ":") {
    throw new RangeError(`TOON header missing colon terminator: ${JSON.stringify(line)}`);
  }
  return { count: declared, cols };
}

function splitCsvRow(line: string): string[] {
  const tokens: string[] = [];
  const n = line.length;
  if (n === 0) return tokens;
  let i = 0;
  while (true) {
    // Skip leading whitespace (defensive — encoder never emits padding).
    while (i < n && line[i] === " ") i++;
    if (i >= n) {
      tokens.push("");
      break;
    }
    if (line[i] === '"') {
      let j = i + 1;
      while (j < n) {
        if (line[j] === "\\" && j + 1 < n) {
          j += 2;
          continue;
        }
        if (line[j] === '"') break;
        j++;
      }
      tokens.push(line.slice(i, j + 1));
      i = j + 1;
      if (i >= n) break;
      if (line[i] === ",") {
        i++;
        continue;
      }
      while (i < n && line[i] !== ",") i++;
      if (i >= n) break;
      i++;
    } else {
      let j = i;
      while (j < n && line[j] !== ",") j++;
      tokens.push(line.slice(i, j));
      i = j;
      if (i >= n) break;
      i++; // consume comma
    }
  }
  return tokens;
}

function decodeQuoted(token: string): string {
  const inner = token.slice(1, -1);
  let out = "";
  let i = 0;
  while (i < inner.length) {
    const ch = inner[i];
    if (ch === "\\" && i + 1 < inner.length) {
      const nxt = inner.charAt(i + 1);
      if (nxt === "\\") out += "\\";
      else if (nxt === '"') out += '"';
      else if (nxt === "n") out += "\n";
      else if (nxt === "r") out += "\r";
      else if (nxt === "t") out += "\t";
      else out += nxt;
      i += 2;
      continue;
    }
    out += ch;
    i++;
  }
  return out;
}

function unquoteIfQuoted(token: string): string {
  if (token.length >= 2 && token[0] === '"' && token[token.length - 1] === '"') {
    return decodeQuoted(token);
  }
  return token;
}

function decodeValue(token: string): unknown {
  if (token.length === 0) return null;
  if (token[0] === '"' && token[token.length - 1] === '"' && token.length >= 2) {
    return decodeQuoted(token);
  }
  if (token === "null") return null;
  if (token === "true") return true;
  if (token === "false") return false;
  // Numeric attempt.
  if (NUMERIC_LIKE_RE.test(token)) {
    if (!token.includes(".") && !/[eE]/.test(token)) {
      const n = Number.parseInt(token, 10);
      if (!Number.isNaN(n)) return n;
    }
    const f = Number.parseFloat(token);
    if (!Number.isNaN(f)) return f;
  }
  // Bare unquoted string — TOON allows it when no quote-triggers fire.
  return token;
}

/**
 * Parse a TOON v3.0 tabular block back into rows + columns.
 *
 * Accepts ONLY the tabular shape that `toonDumps` produces; nested objects
 * / expanded lists are out of scope for the formats module.
 */
export function toonLoads(data: string): {
  rows: Array<Record<string, unknown>>;
  columns: string[];
} {
  const lines = data.split(/\r?\n/);
  let idx = 0;
  while (idx < lines.length && lines[idx]?.trim() === "") idx++;
  if (idx >= lines.length) throw new RangeError("empty TOON payload");

  const { count: declared, cols: colsRegion } = parseHeaderLine(lines[idx] ?? "");
  const columns = colsRegion === "" ? [] : splitCsvRow(colsRegion).map((t) => unquoteIfQuoted(t));

  const rawRows: unknown[][] = [];
  for (const raw of lines.slice(idx + 1)) {
    const line = raw.replace(/\s+$/u, "");
    if (line.trim() === "") continue;
    const stripped = line.replace(/^ +/u, "");
    const tokens = splitCsvRow(stripped);
    if (columns.length > 0 && tokens.length !== columns.length) {
      throw new RangeError(
        `TOON row column count mismatch: expected ${columns.length}, got ${tokens.length}: ${JSON.stringify(stripped)}`,
      );
    }
    rawRows.push(tokens.map((t) => decodeValue(t)));
  }
  if (declared !== rawRows.length) {
    throw new RangeError(`TOON declared row count ${declared} != actual ${rawRows.length}`);
  }
  const rows = rawRows.map((row) => {
    const r: Record<string, unknown> = {};
    for (let i = 0; i < columns.length; i++) {
      r[columns[i] as string] = row[i];
    }
    return r;
  });
  return { rows, columns };
}
