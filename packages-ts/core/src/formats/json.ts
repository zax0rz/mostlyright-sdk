// JSON format — records-form / empty-frame-envelope serialization.
//
// Mirrors `packages/core/src/tradewinds/core/formats/json.py`. Non-empty rows
// emit the records form (`[{col1:v1,col2:v2},...]`); empty rows emit the
// envelope `{columns: [...], data: []}` so column names survive a roundtrip.
//
// The signature `jsonDumps(rows, columns?)` requires `columns` ONLY when
// `rows.length === 0` — otherwise columns are inferred from `Object.keys
// (rows[0])`.

/**
 * Serialize rows to a JSON string.
 *
 * - Non-empty: emits records form `JSON.stringify(rows)`.
 * - Empty: emits envelope `{"columns": [...], "data": []}` — column names
 *   survive the empty-frame roundtrip. Throws RangeError if `columns` is
 *   not provided in the empty case.
 */
export function jsonDumps(
  rows: ReadonlyArray<Record<string, unknown>>,
  columns?: ReadonlyArray<string>,
): string {
  if (rows.length === 0) {
    if (columns === undefined) {
      throw new RangeError(
        "jsonDumps: columns parameter is required when rows is empty (envelope form preserves column order)",
      );
    }
    return JSON.stringify({ columns: [...columns], data: [] });
  }
  return JSON.stringify(rows);
}

/**
 * Parse a JSON string into rows + column-order array.
 *
 * Accepts both the records form (`[{...}, ...]`) and the empty-frame
 * envelope (`{columns, data}`). Returns BOTH `rows` AND `columns` so
 * callers can preserve column order on empty cases.
 */
export function jsonLoads(data: string): {
  rows: Array<Record<string, unknown>>;
  columns: string[];
} {
  const trimmed = data.trimStart();
  if (trimmed.startsWith("{")) {
    const parsed = JSON.parse(data) as { columns?: unknown; data?: unknown };
    if (Array.isArray(parsed.columns) && Array.isArray(parsed.data)) {
      const columns = parsed.columns.map(String);
      const rows = parsed.data as Array<Record<string, unknown>>;
      return { rows, columns };
    }
    throw new RangeError(
      `jsonLoads: envelope form must have {columns: string[], data: object[]}; got ${data.slice(
        0,
        80,
      )}`,
    );
  }
  const parsed = JSON.parse(data);
  if (!Array.isArray(parsed)) {
    throw new RangeError(`jsonLoads: expected array or envelope; got ${typeof parsed}`);
  }
  const rows = parsed as Array<Record<string, unknown>>;
  const columns = rows.length > 0 ? Object.keys(rows[0] as Record<string, unknown>) : [];
  return { rows, columns };
}
